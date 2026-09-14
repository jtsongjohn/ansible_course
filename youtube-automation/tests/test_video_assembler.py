"""video_assembler 의 순수 계산 로직(ffmpeg 렌더링 불필요) 테스트."""
import pytest

from src.pipeline.video_assembler import _hex_to_rgb, _make_gradient_array, resolve_font_path


def test_hex_to_rgb():
    assert _hex_to_rgb("#0b1e3d") == (11, 30, 61)
    assert _hex_to_rgb("1c3f6e") == (28, 63, 110)


def test_make_gradient_array_shape_and_endpoints():
    width, height = 10, 20
    arr = _make_gradient_array(width, height, "#000000", "#ffffff")

    assert arr.shape == (height, width, 3)
    # 맨 윗줄은 color_from(검정)에 가깝고, 맨 아랫줄은 color_to(흰색)에 가까워야 한다.
    assert tuple(arr[0, 0]) == (0, 0, 0)
    assert tuple(arr[-1, 0]) == (255, 255, 255)


def test_resolve_font_path_accepts_direct_file_path(tmp_path):
    fake_font = tmp_path / "MyFont.ttf"
    fake_font.write_bytes(b"not a real font, just needs to exist")

    assert resolve_font_path(str(fake_font)) == str(fake_font)


def test_resolve_font_path_raises_clear_error_when_missing():
    with pytest.raises(RuntimeError, match="한글 폰트 파일을 찾을 수 없습니다"):
        resolve_font_path("이런-폰트는-존재하지-않음")
