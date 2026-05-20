#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "$ROOT_DIR/.." && pwd)"

PYTHON_BIN=""

if [ -f "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif [ -f "$ROOT_DIR/.venv/Scripts/python.exe" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/Scripts/python.exe"
elif [ -f "$WORKSPACE_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$WORKSPACE_DIR/.venv/bin/python"
elif [ -f "$WORKSPACE_DIR/.venv/Scripts/python.exe" ]; then
  PYTHON_BIN="$WORKSPACE_DIR/.venv/Scripts/python.exe"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  printf 'Missing python interpreter for image worker.\n' >&2
  exit 1
fi

printf 'Starting image worker\n'
cd "$ROOT_DIR"
"$PYTHON_BIN" -m src.imgprocessing.worker
