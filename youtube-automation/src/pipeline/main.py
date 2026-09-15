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
from .issue_selector import select_issues
from .narration import synthesize
from .script_generator import generate_script
from .source_fetcher import enrich_issue
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

    if cfg["content_mode"].get("reupload_raw_clips"):
        print(
            "[main] 경고: content_mode.reupload_raw_clips=true 입니다. "
            "원본 뉴스/방송 클립을 그대로 재업로드하는 것은 저작권 침해 리스크가 "
            "매우 높습니다. README.md의 '저작권/법적 리스크' 섹션을 반드시 확인하세요. "
            "이 파이프라인의 video_assembler 는 현재 원본 클립 삽입 기능을 구현하지 "
            "않으며, 항상 자체 배경+자막+나레이션으로만 영상을 만듭니다."
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

        slug = _slugify(issue.keyword)
        work_dir = output_dir / run_date / slug
        work_dir.mkdir(parents=True, exist_ok=True)

        script_path = work_dir / "script.json"
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "channel": cfg["channel"],
                    "issue": issue.keyword,
                    "title": script.title,
                    "hook": script.hook,
                    "body": script.body,
                    "cta": script.cta,
                    "sources": script.sources,
                    "disclaimer": script.disclaimer,
                    "raw_issue_context": enriched,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"[main] 대본 저장: {script_path}")

        tts_cfg = cfg["tts"]
        audio_path = work_dir / "narration.mp3"
        timings = synthesize(
            script.full_narration, tts_cfg["voice"], tts_cfg["rate"], str(audio_path)
        )
        print(f"[main] 나레이션 생성: {audio_path}")

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

        generated_paths.append(str(video_path))

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
