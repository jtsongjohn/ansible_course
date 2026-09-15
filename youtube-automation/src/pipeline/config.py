"""설정 로딩 유틸리티: config.yaml(공통) + config/channels/<channel>.yaml(채널별 오버라이드)
+ .env 를 한 곳에서 읽어온다."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


def _deep_merge(base: dict, override: dict) -> dict:
    """override 의 값으로 base 를 덮어쓰되, dict 는 재귀적으로 병합한다.
    (리스트/문자열 등은 override 쪽이 있으면 통째로 교체)"""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str | Path | None = None, channel: str | None = None) -> dict[str, Any]:
    load_dotenv(REPO_ROOT / ".env")
    cfg_path = Path(path) if path else REPO_ROOT / "config" / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if channel:
        channel_path = REPO_ROOT / "config" / "channels" / f"{channel}.yaml"
        if not channel_path.is_file():
            raise RuntimeError(
                f"채널 설정 파일을 찾을 수 없습니다: {channel_path}. "
                f"config/channels/ 아래에 '{channel}.yaml' 을 만들어주세요."
            )
        with open(channel_path, "r", encoding="utf-8") as f:
            channel_cfg = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, channel_cfg)

    cfg["channel"] = channel or "default"
    cfg["_output_dir"] = str(REPO_ROOT / cfg.get("output_dir", "output"))
    os.makedirs(cfg["_output_dir"], exist_ok=True)
    return cfg


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"환경변수 {name} 가 설정되어 있지 않습니다. .env 파일을 확인하세요 "
            f"(.env.example 참고)."
        )
    return value
