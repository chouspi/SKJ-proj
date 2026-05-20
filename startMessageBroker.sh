#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
  source "$ROOT_DIR/.venv/bin/activate"
elif [ -f "$ROOT_DIR/.venv/Scripts/activate" ]; then
  source "$ROOT_DIR/.venv/Scripts/activate"
fi

if ! command -v uvicorn >/dev/null 2>&1; then
  printf 'Missing uvicorn. Activate/install backend dependencies first.\n' >&2
  exit 1
fi

printf 'Starting message broker on http://127.0.0.1:8001\n'
cd "$ROOT_DIR"
uvicorn src.messagebroker.main:app --reload --host 127.0.0.1 --port 8001
