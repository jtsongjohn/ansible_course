"""
썸네일 생성 모듈
----------------
채널 배경색 + 제목 텍스트로 유튜브 표준 썸네일(1280x720 JPG)을 만든다.
video_assembler.py와 동일한 그라디언트/폰트 로직(imaging.py)을 재사용해
쇼츠 영상과 톤이 일치하도록 한다.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .imaging import make_gradient_array, resolve_font_path

THUMBNAIL_SIZE = (1280, 720)
_MARGIN = 80
_MAX_FONT_SIZE = 108
_MIN_FONT_SIZE = 48


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """단어(공백) 단위로 줄바꿈하되, 단어 하나가 너무 길면 글자 단위로도 쪼갠다."""
    words = text.split(" ")
    lines: list[str] = []
    current = ""

    def width_of(s: str) -> float:
        return draw.textlength(s, font=font)

    for word in words:
        candidate = f"{current} {word}".strip()
        if width_of(candidate) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word

        # 단어 자체가 max_width보다 길면(긴 영단어/숫자 등) 글자 단위로 강제 개행
        while width_of(current) > max_width and len(current) > 1:
            for i in range(len(current) - 1, 0, -1):
                if width_of(current[:i]) <= max_width:
                    lines.append(current[:i])
                    current = current[i:]
                    break
            else:
                break

    if current:
        lines.append(current)
    return lines


def _fit_title(draw: ImageDraw.ImageDraw, title: str, font_path: str, max_width: int, max_height: int):
    """가능한 큰 폰트 크기부터 시도해, 줄바꿈된 제목이 영역 안에 들어가는 조합을 찾는다."""
    for font_size in range(_MAX_FONT_SIZE, _MIN_FONT_SIZE - 1, -4):
        font = ImageFont.truetype(font_path, font_size)
        lines = _wrap_text(draw, title, font, max_width)
        line_height = font.getbbox("가")[3] + 14
        total_height = line_height * len(lines)
        if total_height <= max_height and len(lines) <= 4:
            return font, lines, line_height
    # 최소 크기로도 안 들어가면 그냥 최소 크기로 반환(잘리더라도 진행)
    font = ImageFont.truetype(font_path, _MIN_FONT_SIZE)
    lines = _wrap_text(draw, title, font, max_width)
    line_height = font.getbbox("가")[3] + 14
    return font, lines, line_height


def generate_thumbnail(
    title: str,
    video_cfg: dict,
    out_path: str,
    channel_name: str | None = None,
) -> str:
    width, height = THUMBNAIL_SIZE
    font_path = resolve_font_path(video_cfg.get("font", "NanumGothicBold"))

    bg_array = make_gradient_array(
        width, height, video_cfg["background_color_from"], video_cfg["background_color_to"]
    )
    img = Image.fromarray(bg_array)
    draw = ImageDraw.Draw(img)

    max_width = width - 2 * _MARGIN
    max_height = height - 2 * _MARGIN
    font, lines, line_height = _fit_title(draw, title, font_path, max_width, max_height)

    total_height = line_height * len(lines)
    y = (height - total_height) / 2
    for line in lines:
        line_width = draw.textlength(line, font=font)
        x = (width - line_width) / 2
        draw.text(
            (x, y), line, font=font, fill="white", stroke_width=6, stroke_fill="black"
        )
        y += line_height

    if channel_name:
        small_font = ImageFont.truetype(font_path, 28)
        label = channel_name
        label_width = draw.textlength(label, font=small_font)
        draw.text(
            (width - label_width - 24, height - 44),
            label,
            font=small_font,
            fill="#dddddd",
            stroke_width=3,
            stroke_fill="black",
        )

    img.save(out_path, "JPEG", quality=92)
    return out_path
