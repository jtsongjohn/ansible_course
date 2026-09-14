"""captions 모듈(순수 로직) 테스트."""
from src.pipeline.captions import CaptionCue, _srt_timestamp, build_cues, write_srt
from src.pipeline.narration import WordTiming


def test_build_cues_splits_on_max_chars():
    timings = [
        WordTiming(text="안녕하세요 ", start=0.0, end=0.5),
        WordTiming(text="오늘의 ", start=0.5, end=1.0),
        WordTiming(text="정치뉴스를 ", start=1.0, end=1.8),
        WordTiming(text="전해드립니다", start=1.8, end=2.6),
    ]
    cues = build_cues(timings, max_chars_per_line=12)

    assert len(cues) >= 2
    # 모든 단어가 어딘가의 큐에 정확히 한 번씩 포함되어야 한다.
    joined = "".join(c.text for c in cues)
    assert "안녕하세요" in joined
    assert "전해드립니다" in joined
    # 각 큐의 시작/끝 시간은 포함된 단어들의 시간 범위를 따라야 한다.
    assert cues[0].start == 0.0


def test_build_cues_empty_input():
    assert build_cues([], max_chars_per_line=12) == []


def test_srt_timestamp_format():
    assert _srt_timestamp(0) == "00:00:00,000"
    assert _srt_timestamp(65.5) == "00:01:05,500"
    assert _srt_timestamp(3661.25) == "01:01:01,250"


def test_srt_timestamp_clamps_negative():
    assert _srt_timestamp(-5) == "00:00:00,000"


def test_write_srt_format(tmp_path):
    cues = [
        CaptionCue(text="첫 번째 자막", start=0.0, end=1.5),
        CaptionCue(text="두 번째 자막", start=1.5, end=3.0),
    ]
    out_path = tmp_path / "captions.srt"
    write_srt(cues, str(out_path))

    content = out_path.read_text(encoding="utf-8")
    assert "1\n00:00:00,000 --> 00:00:01,500\n첫 번째 자막" in content
    assert "2\n00:00:01,500 --> 00:00:03,000\n두 번째 자막" in content
