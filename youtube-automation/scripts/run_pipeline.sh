#!/usr/bin/env bash
# 파이프라인 실행 스크립트 (수동 실행 / cron / systemd timer 공용)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
  source venv/bin/activate
fi

python -m src.pipeline.main
