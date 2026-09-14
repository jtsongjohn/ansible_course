"""
자막 모듈
---------
narration.synthesize() 가 반환한 단어별 타이밍을 기반으로,
화면에 표시할 자막 "큐(cue)" 목록과 .srt 파일을 만든다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .narration import WordTiming


@dataclass
class CaptionCue:
    text: str
    start: float
    end: float


def build_cues(timings: list[WordTiming], max_chars_per_line: int = 18) -> list[CaptionCue]:
    """단어 타이밍들을 max_chars_per_line 기준으로 묶어 자막 큐를 만든다."""
    cues: list[CaptionCue] = []
    buf: list[WordTiming] = []
    buf_len = 0

    def flush():
        nonlocal buf, buf_len
        if not buf:
            return
        text = "".join(w.text for w in buf).strip()
        cues.append(CaptionCue(text=text, start=buf[0].start, end=buf[-1].end))
        buf = []
        buf_len = 0

    for w in timings:
        word_len = len(w.text)
        if buf and buf_len + word_len > max_chars_per_line:
            flush()
        buf.append(w)
        buf_len += word_len

    flush()
    return cues


def _srt_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(cues: list[CaptionCue], out_path: str) -> None:
    lines = []
    for i, cue in enumerate(cues, start=1):
        lines.append(str(i))
        lines.append(f"{_srt_timestamp(cue.start)} --> {_srt_timestamp(cue.end)}")
        lines.append(cue.text)
        lines.append("")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
