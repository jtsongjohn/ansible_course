"""thumbnail.py 테스트. fonts-nanum이 설치된 환경에서만 실제 렌더링을 검증하고,
없는 환경(CI 등)에서는 자동으로 건너뛴다."""
import pytest
from PIL import Image

from src.pipeline.imaging import resolve_font_path
from src.pipeline.thumbnail import THUMBNAIL_SIZE, generate_thumbnail


def _has_nanum_font() -> bool:
    try:
        resolve_font_path("NanumGothicBold")
        return True
    except RuntimeError:
        return False


@pytest.mark.skipif(not _has_nanum_font(), reason="fonts-nanum이 설치되어 있지 않음")
def test_generate_thumbnail_creates_correct_size_jpeg(tmp_path):
    out_path = tmp_path / "thumb.jpg"
    video_cfg = {
        "background_color_from": "#0b1e3d",
        "background_color_to": "#1c3f6e",
        "font": "NanumGothicBold",
    }

    generate_thumbnail(
        title="예산안 처리, 왜 또 늦어질까?",
        video_cfg=video_cfg,
        out_path=str(out_path),
        channel_name="테스트 채널",
    )

    assert out_path.exists()
    with Image.open(out_path) as img:
        assert img.size == THUMBNAIL_SIZE
        assert img.format == "JPEG"


@pytest.mark.skipif(not _has_nanum_font(), reason="fonts-nanum이 설치되어 있지 않음")
def test_generate_thumbnail_wraps_long_title(tmp_path):
    out_path = tmp_path / "thumb_long.jpg"
    video_cfg = {
        "background_color_from": "#3d0b0b",
        "background_color_to": "#6e1c1c",
        "font": "NanumGothicBold",
    }

    # 아주 긴 제목도 예외 없이 처리되어야 한다 (내부적으로 줄바꿈/폰트 축소).
    long_title = "이것은 아주 길고 긴 유튜브 쇼츠 제목입니다 정말로 많이 깁니다 그래도 처리되어야 합니다"
    generate_thumbnail(title=long_title, video_cfg=video_cfg, out_path=str(out_path))

    assert out_path.exists()
