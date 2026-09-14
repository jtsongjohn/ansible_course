"""
영상 조립 모듈
--------------
나레이션 오디오 + 자막 큐 + (원본 클립 대신) 그라디언트 배경을 합성해
세로형(9:16) 쇼츠 mp4를 만든다.

저작권 리스크를 낮추기 위해 기본값은 뉴스/국회 원본 영상을 그대로 쓰지 않고
자체 배경 + 자막 + 음성 나레이션으로 영상을 구성한다.
(config.yaml 의 content_mode.reupload_raw_clips 참고)

moviepy 2.x 기준(구버전 1.x의 `moviepy.editor`/`set_*` API와 다름)으로 작성됨.
TextClip은 ImageMagick 없이 Pillow로 직접 렌더링하지만, 한글을 제대로 그리려면
실제 한글 폰트 "파일 경로"(TTF/OTF)가 필요하다 — 폰트 "이름"만으로는 동작하지
않는다. ansible/roles/youtube_pipeline 에서 fonts-nanum 패키지를 설치해준다.
"""
from __future__ import annotations

import glob

import numpy as np
from moviepy import AudioFileClip, CompositeVideoClip, ImageClip, TextClip

from .captions import CaptionCue

# fonts-nanum(Ubuntu/Debian) 및 Homebrew(macOS)로 설치했을 때 흔히 위치하는 경로들.
# config.yaml 의 video.font 에 절대경로를 직접 지정하면 이 목록보다 우선한다.
_FONT_SEARCH_PATTERNS = [
    "/usr/share/fonts/truetype/nanum/{name}.ttf",
    "/usr/share/fonts/opentype/nanum/{name}.ttf",
    "/usr/local/share/fonts/{name}.ttf",
    "/opt/homebrew/Caskroom/font-nanum-gothic/*/{name}.ttf",
    "/Library/Fonts/{name}.ttf",
    "~/Library/Fonts/{name}.ttf",
]


def resolve_font_path(font_cfg: str) -> str:
    """config.yaml 의 video.font 값을 실제 폰트 파일 경로로 해석한다.

    - 이미 존재하는 파일 경로면 그대로 사용.
    - 아니면 폰트 "이름"으로 간주해 흔한 설치 경로들을 뒤진다.
    - 그래도 못 찾으면, 한글이 깨진 채로(빈 네모) 렌더링되는 것을 방지하기 위해
      명확한 에러를 낸다.
    """
    from pathlib import Path

    p = Path(font_cfg).expanduser()
    if p.is_file():
        return str(p)

    for pattern in _FONT_SEARCH_PATTERNS:
        expanded = str(Path(pattern.format(name=font_cfg)).expanduser())
        matches = glob.glob(expanded)
        if matches:
            return matches[0]

    raise RuntimeError(
        f"한글 폰트 파일을 찾을 수 없습니다 (설정값: '{font_cfg}'). "
        "Ubuntu/Debian: `sudo apt install fonts-nanum` 후 "
        "video.font 를 'NanumGothicBold'로 두거나, "
        "`/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf` 처럼 "
        "config.yaml 에 절대경로를 직접 지정하세요."
    )


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


def _make_text_clip(text: str, font_size: int, color: str, font_path: str, width: int) -> TextClip:
    return TextClip(
        font=font_path,
        text=text,
        font_size=font_size,
        color=color,
        method="caption",
        size=(int(width * 0.85), None),
        text_align="center",
        horizontal_align="center",
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
    font_path = resolve_font_path(video_cfg.get("font", "NanumGothicBold"))

    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    bg_array = _make_gradient_array(
        width, height, video_cfg["background_color_from"], video_cfg["background_color_to"]
    )
    background = ImageClip(bg_array).with_duration(duration)

    layers = [background]

    title_clip = (
        _make_text_clip(title, font_size=64, color="white", font_path=font_path, width=width)
        .with_position(("center", int(height * 0.08)))
        .with_start(0)
        .with_duration(min(3.0, duration))
    )
    layers.append(title_clip)

    for cue in cues:
        cue_duration = max(cue.end - cue.start, 0.3)
        caption_clip = (
            _make_text_clip(cue.text, font_size=56, color="yellow", font_path=font_path, width=width)
            .with_position(("center", int(height * 0.72)))
            .with_start(cue.start)
            .with_duration(cue_duration)
        )
        layers.append(caption_clip)

    disclaimer_clip = (
        _make_text_clip(disclaimer, font_size=28, color="#cccccc", font_path=font_path, width=width)
        .with_position(("center", int(height * 0.94)))
        .with_start(0)
        .with_duration(duration)
    )
    layers.append(disclaimer_clip)

    video = CompositeVideoClip(layers, size=(width, height)).with_audio(audio_clip)
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
