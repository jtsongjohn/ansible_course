"""설정 로딩 유틸리티: config.yaml + .env 를 한 곳에서 읽어온다."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    load_dotenv(REPO_ROOT / ".env")
    cfg_path = Path(path) if path else REPO_ROOT / "config" / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
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
