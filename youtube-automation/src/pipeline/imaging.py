"""
이미지/폰트 공용 유틸리티
------------------------
video_assembler.py(쇼츠 영상)와 thumbnail.py(썸네일)가 공통으로 쓰는
그라디언트 배경 생성 + 한글 폰트 파일 경로 탐색 로직을 모아둔다.
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np

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


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def make_gradient_array(width: int, height: int, color_from: str, color_to: str) -> np.ndarray:
    """세로 방향 선형 그라디언트를 (height, width, 3) uint8 배열로 만든다."""
    c1 = np.array(hex_to_rgb(color_from), dtype=float)
    c2 = np.array(hex_to_rgb(color_to), dtype=float)
    ramp = np.linspace(0, 1, height).reshape(height, 1, 1)
    gradient = (c1 * (1 - ramp) + c2 * ramp).astype("uint8")
    gradient = np.repeat(gradient, width, axis=1)
    return gradient
