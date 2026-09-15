"""
파이프라인 오케스트레이터
------------------------
이슈 선정 -> 소스 보강 -> 대본 생성 -> TTS 나레이션 -> 자막 -> 영상 조립
까지 전 과정을 실행한다. 업로드는 하지 않으며, output/ 아래에 검수용
결과물(mp4 + 대본 json + srt)을 생성한다.

실행:
    python -m src.pipeline.main                  # 기본 config.yaml만 사용
    python -m src.pipeline.main --channel right   # config/channels/right.yaml 오버레이
    python -m src.pipeline.main --channel left    # config/channels/left.yaml 오버레이
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from .captions import build_cues, write_srt
from .config import load_config
from .fact_checker import verify_script
from .issue_selector import select_issues
from .narration import synthesize
from .script_generator import generate_script
from .source_fetcher import enrich_issue
from .thumbnail import generate_thumbnail
from .video_assembler import assemble_video


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w가-힣]+", "-", text).strip("-")
    return text[:40] or "issue"


def run_pipeline(channel: str | None = None) -> list[str]:
    cfg = load_config(channel=channel)
    channel_name = cfg.get("channel_name", "기본 채널")
    print(f"[main] 채널: {channel_name} (channel={cfg['channel']})")

    output_dir = Path(cfg["_output_dir"])
    run_date = datetime.now().strftime("%Y%m%d")

    manual_closing_remark = cfg["content_mode"].get("manual_closing_remark", False)

    if cfg["content_mode"].get("reupload_raw_clips"):
        print(
            "[main] 경고: content_mode.reupload_raw_clips=true 입니다. "
            "finalize.py가 script.json의 source_clip_path에 지정된 클립을 실제로 "
            "영상에 이어붙입니다. 그 클립을 저작권상 안전하게 확보했는지는 전적으로 "
            "사용자 책임입니다 — README.md의 '저작권/법적 리스크' 섹션을 반드시 "
            "확인하세요."
        )

    issues = select_issues(cfg)
    if not issues:
        print("[main] 선정된 이슈가 없어 종료합니다.")
        return []

    generated_paths: list[str] = []

    for issue in issues:
        print(f"\n[main] === 이슈 처리 시작: {issue.keyword} ===")
        enriched = enrich_issue(issue)

        sg_cfg = cfg["script_generation"]
        script = generate_script(
            enriched,
            model=sg_cfg["model"],
            target_seconds=sg_cfg["target_seconds"],
            max_words=sg_cfg["max_words"],
            stance_prompt=sg_cfg.get("stance_prompt"),
        )

        fact_check_result = None
        if sg_cfg.get("fact_check_enabled"):
            fact_check_result = verify_script(script, enriched, model=sg_cfg["model"])
            if not fact_check_result.passed:
                print(
                    f"[main] ⚠ 팩트체크 경고: {fact_check_result.notes} "
                    f"(지적된 문장: {fact_check_result.flagged_claims})"
                )
            else:
                print("[main] 팩트체크 통과")

        slug = _slugify(issue.keyword)
        work_dir = output_dir / run_date / slug
        work_dir.mkdir(parents=True, exist_ok=True)

        script_path = work_dir / "script.json"
        script_data = {
            "channel": cfg["channel"],
            "issue": issue.keyword,
            "title": script.title,
            "hook": script.hook,
            "body": script.body,
            "cta": script.cta,
            "sources": script.sources,
            "disclaimer": script.disclaimer,
            "fact_check": fact_check_result.to_dict() if fact_check_result else None,
            "raw_issue_context": enriched,
        }
        if manual_closing_remark:
            # cta는 참고용 AI 초안으로만 남겨두고, 실제 마무리("한마디")는
            # 사람이 아래 두 필드를 채운 뒤 finalize.py로 반영한다.
            script_data["closing_remark"] = ""
            script_data["source_clip_path"] = ""
            script_data["clip_source_label"] = ""

        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
        print(f"[main] 대본 저장: {script_path}")

        tts_cfg = cfg["tts"]
        audio_path = work_dir / "narration.mp3"
        narration_text = script.hook_and_body if manual_closing_remark else script.full_narration
        timings = synthesize(
            narration_text, tts_cfg["voice"], tts_cfg["rate"], str(audio_path)
        )
        print(f"[main] 나레이션 생성({'초안, cta 제외' if manual_closing_remark else '완성'}): {audio_path}")

        video_cfg = cfg["video"]
        cues = build_cues(timings, video_cfg["caption_max_chars_per_line"])
        srt_path = work_dir / "captions.srt"
        write_srt(cues, str(srt_path))
        print(f"[main] 자막 생성: {srt_path}")

        video_path = work_dir / "short.mp4"
        assemble_video(
            title=script.title,
            disclaimer=script.disclaimer,
            audio_path=str(audio_path),
            cues=cues,
            video_cfg=video_cfg,
            out_path=str(video_path),
        )
        print(f"[main] 영상 생성 완료: {video_path}")

        thumbnail_path = work_dir / "thumbnail.jpg"
        generate_thumbnail(
            title=script.title,
            video_cfg=video_cfg,
            out_path=str(thumbnail_path),
            channel_name=cfg.get("channel_name"),
        )
        print(f"[main] 썸네일 생성 완료: {thumbnail_path}")

        generated_paths.append(str(video_path))

        if manual_closing_remark:
            print(
                f"[main] → '{script_path}' 의 closing_remark(한마디)를 채운 뒤 "
                f"다음 명령으로 최종본을 만드세요:\n"
                f"    python -m src.pipeline.finalize --script {script_path}"
            )

    print(f"\n[main] 총 {len(generated_paths)}개 영상 생성 완료. "
          f"업로드 전 반드시 직접 검수하세요 (사실관계/편향성/저작권).")
    return generated_paths


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="유튜브 정치 쇼츠 자동화 파이프라인")
    parser.add_argument(
        "--channel",
        default=None,
        help="config/channels/<channel>.yaml 오버레이 이름 (예: right, left). 생략 시 config.yaml만 사용.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_pipeline(channel=args.channel)
