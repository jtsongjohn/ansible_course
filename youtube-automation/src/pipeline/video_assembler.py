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

from moviepy import AudioFileClip, CompositeVideoClip, ImageClip, TextClip

from .captions import CaptionCue
from .imaging import make_gradient_array, resolve_font_path


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

    bg_array = make_gradient_array(
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
