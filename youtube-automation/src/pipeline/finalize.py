"""
마무리(한마디 반영) 단계
------------------------
content_mode.manual_closing_remark: true 로 실행한 main.py는 hook+body만으로
"초안"(script.json + narration.mp3 + short.mp4)을 만들고, cta 자리에
사람이 직접 쓸 closing_remark(한마디)를 빈칸으로 남겨둔다.

이 스크립트는 사람이 script.json을 직접 편집(closing_remark를 채우고,
필요하면 source_clip_path/clip_source_label도 채운)한 뒤 실행해서,
"한마디"까지 포함한 나레이션/자막/영상을 최종본으로 다시 만든다.

closing_remark는 녹음이 아니라 "텍스트"다 — 채널의 TTS 목소리가 그대로
읽어주므로, 본문과 자연스럽게 이어지는 하나의 목소리로 나온다.

사용법:
    python -m src.pipeline.finalize --script output/right/20260101/이슈/script.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .captions import build_cues, write_srt
from .config import load_config
from .narration import synthesize
from .video_assembler import assemble_video


def finalize(script_path: str) -> str:
    path = Path(script_path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    closing_remark = (data.get("closing_remark") or "").strip()
    if not closing_remark:
        raise SystemExit(
            f"'{path}' 의 closing_remark 필드가 비어 있습니다. "
            "먼저 본인이 쓴 '한마디'를 채워넣고 다시 실행하세요."
        )

    channel = data.get("channel")
    channel = None if channel in (None, "default") else channel
    cfg = load_config(channel=channel)
    work_dir = path.parent

    narration_text = " ".join(
        [data["hook"], data["body"], closing_remark]
    ).strip()

    tts_cfg = cfg["tts"]
    audio_path = work_dir / "narration_final.mp3"
    timings = synthesize(narration_text, tts_cfg["voice"], tts_cfg["rate"], str(audio_path))
    print(f"[finalize] 최종 나레이션 생성: {audio_path}")

    video_cfg = cfg["video"]
    cues = build_cues(timings, video_cfg["caption_max_chars_per_line"])
    srt_path = work_dir / "captions_final.srt"
    write_srt(cues, str(srt_path))
    print(f"[finalize] 최종 자막 생성: {srt_path}")

    clip_path = (data.get("source_clip_path") or "").strip() or None
    if clip_path:
        if not cfg["content_mode"].get("reupload_raw_clips"):
            raise SystemExit(
                f"source_clip_path='{clip_path}' 가 지정되어 있지만, "
                "config의 content_mode.reupload_raw_clips가 꺼져 있어 클립을 "
                "삽입하지 않습니다. 저작권 리스크를 확인한 뒤 의도적으로 켜세요"
                "(README '저작권/법적 리스크' 섹션 참고)."
            )
        if not Path(clip_path).is_file():
            raise SystemExit(f"source_clip_path로 지정된 파일을 찾을 수 없습니다: {clip_path}")

    video_path = work_dir / "short_final.mp4"
    assemble_video(
        title=data["title"],
        disclaimer=data["disclaimer"],
        audio_path=str(audio_path),
        cues=cues,
        video_cfg=video_cfg,
        out_path=str(video_path),
        clip_path=clip_path,
        clip_source_label=(data.get("clip_source_label") or "").strip() or None,
    )
    print(f"[finalize] 최종 영상 생성 완료: {video_path}")
    print("[finalize] 업로드 전 반드시 직접 검수하세요 (사실관계/편향성/저작권).")
    return str(video_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="closing_remark(한마디)를 반영해 최종 쇼츠 영상을 만든다"
    )
    parser.add_argument("--script", required=True, help="main.py가 생성한 script.json 경로")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    finalize(args.script)
