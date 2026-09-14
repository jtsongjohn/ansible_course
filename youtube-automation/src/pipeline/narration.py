"""
나레이션(TTS) 모듈
------------------
edge-tts(무료, API 키 불필요)로 대본을 음성으로 합성하고,
단어 단위 타임스탬프(WordBoundary)를 함께 수집해 자막 동기화에 사용한다.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import edge_tts


@dataclass
class WordTiming:
    text: str
    start: float  # seconds
    end: float  # seconds


async def _synthesize_async(
    text: str, voice: str, rate: str, out_audio_path: str
) -> list[WordTiming]:
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    timings: list[WordTiming] = []

    with open(out_audio_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10_000_000  # 100ns 단위 -> 초
                duration = chunk["duration"] / 10_000_000
                timings.append(
                    WordTiming(text=chunk["text"], start=start, end=start + duration)
                )

    return timings


def synthesize(text: str, voice: str, rate: str, out_audio_path: str) -> list[WordTiming]:
    """동기 래퍼. mp3 파일을 out_audio_path 에 쓰고, 단어별 타이밍 리스트를 반환한다."""
    return asyncio.run(_synthesize_async(text, voice, rate, out_audio_path))
