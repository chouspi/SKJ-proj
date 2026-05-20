#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/src/web"

if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
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

if ! command -v npm >/dev/null 2>&1; then
  printf 'Missing npm. Install Node.js and npm first.\n' >&2
  exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  printf 'Installing frontend dependencies...\n'
  npm install --prefix "$FRONTEND_DIR"
fi

cleanup() {
  if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi

  if [ -n "${FRONTEND_PID:-}" ] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

printf 'Applying database migrations\n'
(
  cd "$ROOT_DIR"
  alembic upgrade head
)

printf 'Starting backend on http://127.0.0.1:8000\n'
(
  cd "$ROOT_DIR"
  uvicorn src.S3_Storage.main:app --reload --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

printf 'Starting frontend on http://127.0.0.1:5173\n'
(
  cd "$FRONTEND_DIR"
  npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
) &
FRONTEND_PID=$!

wait -n "$BACKEND_PID" "$FRONTEND_PID"
