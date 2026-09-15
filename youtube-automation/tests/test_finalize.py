"""finalize.py 의 제어 흐름(가드 조건) 테스트. 실제 TTS/영상 렌더링은
모킹해서 network/ffmpeg 없이 로직만 검증한다."""
import json
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.finalize import finalize


def _write_script(tmp_path, **overrides) -> str:
    data = {
        "channel": "default",
        "issue": "테스트 이슈",
        "title": "테스트 제목",
        "hook": "훅입니다",
        "body": "본문입니다",
        "cta": "AI가 쓴 초안 마무리",
        "sources": ["연합뉴스"],
        "disclaimer": "테스트 고지",
        "closing_remark": "",
        "source_clip_path": "",
        "clip_source_label": "",
    }
    data.update(overrides)
    path = tmp_path / "script.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


_FAKE_CFG = {
    "channel": "default",
    "tts": {"voice": "ko-KR-InJoonNeural", "rate": "+0%"},
    "video": {
        "resolution": [1080, 1920],
        "fps": 30,
        "caption_max_chars_per_line": 18,
        "background_color_from": "#000000",
        "background_color_to": "#111111",
        "font": "NanumGothicBold",
    },
    "content_mode": {"reupload_raw_clips": False},
}


def test_finalize_raises_when_closing_remark_empty(tmp_path):
    script_path = _write_script(tmp_path)  # closing_remark 기본값이 빈 문자열

    with pytest.raises(SystemExit, match="closing_remark 필드가 비어"):
        finalize(script_path)


@patch("src.pipeline.finalize.assemble_video")
@patch("src.pipeline.finalize.write_srt")
@patch("src.pipeline.finalize.build_cues", return_value=[])
@patch("src.pipeline.finalize.synthesize", return_value=[])
@patch("src.pipeline.finalize.load_config", return_value=_FAKE_CFG)
def test_finalize_rejects_clip_when_reupload_disabled(
    mock_load_config, mock_synth, mock_cues, mock_srt, mock_assemble, tmp_path
):
    fake_clip = tmp_path / "clip.mp4"
    fake_clip.write_bytes(b"fake")
    script_path = _write_script(
        tmp_path, closing_remark="이건 제 한마디입니다", source_clip_path=str(fake_clip)
    )

    with pytest.raises(SystemExit, match="reupload_raw_clips가 꺼져"):
        finalize(script_path)

    mock_assemble.assert_not_called()


@patch("src.pipeline.finalize.assemble_video")
@patch("src.pipeline.finalize.write_srt")
@patch("src.pipeline.finalize.build_cues", return_value=[])
@patch("src.pipeline.finalize.synthesize", return_value=[])
@patch("src.pipeline.finalize.load_config")
def test_finalize_rejects_missing_clip_file(
    mock_load_config, mock_synth, mock_cues, mock_srt, mock_assemble, tmp_path
):
    cfg = dict(_FAKE_CFG)
    cfg["content_mode"] = {"reupload_raw_clips": True}
    mock_load_config.return_value = cfg

    script_path = _write_script(
        tmp_path,
        closing_remark="이건 제 한마디입니다",
        source_clip_path=str(tmp_path / "does-not-exist.mp4"),
    )

    with pytest.raises(SystemExit, match="파일을 찾을 수 없습니다"):
        finalize(script_path)

    mock_assemble.assert_not_called()


@patch("src.pipeline.finalize.assemble_video")
@patch("src.pipeline.finalize.write_srt")
@patch("src.pipeline.finalize.build_cues", return_value=[])
@patch("src.pipeline.finalize.synthesize", return_value=[])
@patch("src.pipeline.finalize.load_config", return_value=_FAKE_CFG)
def test_finalize_happy_path_without_clip(
    mock_load_config, mock_synth, mock_cues, mock_srt, mock_assemble, tmp_path
):
    script_path = _write_script(tmp_path, closing_remark="이건 제 한마디입니다")

    result = finalize(script_path)

    assert result.endswith("short_final.mp4")
    # 나레이션에 hook+body+closing_remark 가 모두 이어붙여져야 하고, cta(AI 초안)는 빠져야 한다.
    narration_text = mock_synth.call_args[0][0]
    assert "훅입니다" in narration_text
    assert "본문입니다" in narration_text
    assert "이건 제 한마디입니다" in narration_text
    assert "AI가 쓴 초안 마무리" not in narration_text

    mock_assemble.assert_called_once()
    assert mock_assemble.call_args.kwargs["clip_path"] is None
