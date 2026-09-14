"""
영상 조립 모듈
--------------
나레이션 오디오 + 자막 큐 + (원본 클립 대신) 그라디언트 배경을 합성해
세로형(9:16) 쇼츠 mp4를 만든다.

저작권 리스크를 낮추기 위해 기본값은 뉴스/국회 원본 영상을 그대로 쓰지 않고
자체 배경 + 자막 + 음성 나레이션으로 영상을 구성한다.
(config.yaml 의 content_mode.reupload_raw_clips 참고)

필요 시스템 패키지: ffmpeg, ImageMagick, 한글 폰트(예: fonts-nanum)
-> ansible/roles/youtube_pipeline 에서 자동 설치한다.
"""
from __future__ import annotations

import numpy as np
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
)
from PIL import Image

from .captions import CaptionCue


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _make_gradient_array(width: int, height: int, color_from: str, color_to: str) -> np.ndarray:
    c1 = np.array(_hex_to_rgb(color_from), dtype=float)
    c2 = np.array(_hex_to_rgb(color_to), dtype=float)
    ramp = np.linspace(0, 1, height).reshape(height, 1, 1)
    gradient = (c1 * (1 - ramp) + c2 * ramp).astype("uint8")
    gradient = np.repeat(gradient, width, axis=1)
    return gradient


def _safe_text_clip(text: str, fontsize: int, color: str, font: str, width: int) -> TextClip:
    try:
        return TextClip(
            text,
            fontsize=fontsize,
            color=color,
            font=font,
            method="caption",
            size=(int(width * 0.85), None),
            align="center",
        )
    except Exception:
        # 지정 폰트/ImageMagick 설정 문제 시 기본 폰트로 재시도
        return TextClip(
            text,
            fontsize=fontsize,
            color=color,
            method="caption",
            size=(int(width * 0.85), None),
            align="center",
        )


def assemble_video(
    title: str,
    disclaimer: str,
    audio_path: str,
    cues: list[CaptionCue],
    video_cfg: dict,
    out_path: str,
) -> str:
    width, height = video_cfg["resolution"]
    fps = video_cfg["fps"]
    font = video_cfg.get("font", "NanumGothicBold")

    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    bg_array = _make_gradient_array(
        width, height, video_cfg["background_color_from"], video_cfg["background_color_to"]
    )
    background = ImageClip(bg_array).set_duration(duration)

    layers = [background]

    title_clip = (
        _safe_text_clip(title, fontsize=64, color="white", font=font, width=width)
        .set_position(("center", int(height * 0.08)))
        .set_start(0)
        .set_duration(min(3.0, duration))
    )
    layers.append(title_clip)

    for cue in cues:
        cue_duration = max(cue.end - cue.start, 0.3)
        caption_clip = (
            _safe_text_clip(cue.text, fontsize=56, color="yellow", font=font, width=width)
            .set_position(("center", int(height * 0.72)))
            .set_start(cue.start)
            .set_duration(cue_duration)
        )
        layers.append(caption_clip)

    disclaimer_clip = (
        _safe_text_clip(disclaimer, fontsize=28, color="#cccccc", font=font, width=width)
        .set_position(("center", int(height * 0.94)))
        .set_start(0)
        .set_duration(duration)
    )
    layers.append(disclaimer_clip)

    video = CompositeVideoClip(layers, size=(width, height)).set_audio(audio_clip)
    video.write_videofile(
        out_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        logger=None,
    )

    for clip in layers:
        clip.close()
    audio_clip.close()

    return out_path
