#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
  source "$ROOT_DIR/.venv/bin/activate"
fi

if ! command -v uvicorn >/dev/null 2>&1; then
  printf 'Missing uvicorn. Activate/install backend dependencies first.\n' >&2
  exit 1
fi

if ! command -v alembic >/dev/null 2>&1; then
  printf 'Missing alembic. Install backend dependencies first.\n' >&2
  exit 1
fi

printf 'Applying database migrations\n'
cd "$ROOT_DIR"
alembic upgrade head

printf 'Starting S3 Gateway on http://127.0.0.1:8000\n'
cd "$ROOT_DIR"
uvicorn src.S3_Storage.main:app --reload --host 127.0.0.1 --port 8000
