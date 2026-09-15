"""config.py 의 base+channel 병합 로직 테스트 (네트워크/API 키 불필요)."""
import pytest

from src.pipeline.config import load_config


def test_load_config_without_channel_uses_defaults():
    cfg = load_config()
    assert cfg["channel"] == "default"
    assert cfg["issue_selection"]["watch_keywords"] == []
    assert "stance_prompt" not in cfg["script_generation"]


def test_load_config_right_channel_overlay():
    cfg = load_config(channel="right")
    assert cfg["channel"] == "right"
    assert cfg["channel_name"] == "우파 해설 채널"
    assert cfg["output_dir"] == "output/right"
    assert "보수" in cfg["script_generation"]["stance_prompt"]
    # base에만 있는 값은 그대로 상속되어야 한다.
    assert cfg["script_generation"]["model"] == "claude-sonnet-5"
    assert cfg["tts"]["engine"] == "edge-tts"


def test_load_config_left_channel_overlay():
    cfg = load_config(channel="left")
    assert cfg["channel"] == "left"
    assert cfg["channel_name"] == "좌파 해설 채널"
    assert cfg["output_dir"] == "output/left"
    assert "진보" in cfg["script_generation"]["stance_prompt"]


def test_load_config_right_and_left_have_distinct_visuals():
    right = load_config(channel="right")
    left = load_config(channel="left")
    assert right["video"]["background_color_from"] != left["video"]["background_color_from"]


def test_load_config_unknown_channel_raises_clear_error():
    with pytest.raises(RuntimeError, match="채널 설정 파일을 찾을 수 없습니다"):
        load_config(channel="does-not-exist")
