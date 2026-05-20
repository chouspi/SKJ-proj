#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/src/web"
VENV_DIR="$ROOT_DIR/.venv"

# ---------- dependency check ----------

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  printf 'Missing python. Install Python 3.10+ first.\n' >&2
  exit 1
fi

PYTHON=$(command -v python3 || command -v python)

if ! command -v npm >/dev/null 2>&1; then
  printf 'Missing npm. Install Node.js and npm first.\n' >&2
  exit 1
fi

# ---------- Python virtual environment ----------

if [ ! -f "$VENV_DIR/bin/activate" ]; then
  printf 'Creating Python virtual environment...\n'
  $PYTHON -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# ---------- install Python dependencies ----------

PYTHON_DEPS_MISSING=0
for req in "$ROOT_DIR/src/S3_Storage/requirements.txt" \
           "$ROOT_DIR/src/messagebroker/requirements.txt" \
           "$ROOT_DIR/src/haystack/requirements.txt" \
           "$ROOT_DIR/src/imgprocessing/requirements.txt"; do
  if [ -f "$req" ]; then
    pip install --quiet -r "$req" 2>/dev/null || PYTHON_DEPS_MISSING=1
  fi
done

if [ "$PYTHON_DEPS_MISSING" -ne 0 ]; then
  printf 'Installing Python dependencies...\n'
  for req in "$ROOT_DIR/src/S3_Storage/requirements.txt" \
             "$ROOT_DIR/src/messagebroker/requirements.txt" \
             "$ROOT_DIR/src/haystack/requirements.txt" \
             "$ROOT_DIR/src/imgprocessing/requirements.txt"; do
    if [ -f "$req" ]; then
      pip install -r "$req"
    fi
  done
fi

# ---------- install frontend dependencies ----------

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  printf 'Installing frontend dependencies...\n'
  npm install --prefix "$FRONTEND_DIR"
fi

# ---------- database migrations ----------

printf 'Applying database migrations\n'
cd "$ROOT_DIR"
alembic upgrade head

# ---------- helper: wait for port ----------

wait_for_port() {
  local host="$1" port="$2" timeout="${3:-20}"
  local waited=0
  while [ $waited -lt $timeout ]; do
    if python -c "import urllib.request; urllib.request.urlopen('http://$host:$port/')" 2>/dev/null; then
      return 0
    fi
    sleep 1
    waited=$((waited + 1))
  done
  printf '  timeout, continuing...\n'
}

# ---------- start services ----------

cleanup() {
  for pid in "${BROKER_PID:-}" "${HAYSTACK_PID:-}" "${IMG_WORKER_PID:-}" "${BACKEND_PID:-}" "${FRONTEND_PID:-}"; do
    if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
}

trap cleanup EXIT INT TERM

printf 'Starting message broker on http://127.0.0.1:8001\n'
(
  cd "$ROOT_DIR"
  uvicorn src.messagebroker.main:app --reload --host 127.0.0.1 --port 8001
) &
BROKER_PID=$!
printf '  cekam na broker...\n'
wait_for_port 127.0.0.1 8001

printf 'Starting Haystack node on http://127.0.0.1:8002\n'
(
  cd "$ROOT_DIR"
  uvicorn src.haystack.main:app --reload --host 127.0.0.1 --port 8002
) &
HAYSTACK_PID=$!
printf '  cekam na haystack...\n'
wait_for_port 127.0.0.1 8002

printf 'Starting backend on http://127.0.0.1:8000\n'
(
  cd "$ROOT_DIR"
  uvicorn src.S3_Storage.main:app --reload --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!
printf '  cekam na backend...\n'
wait_for_port 127.0.0.1 8000

printf 'Starting image worker\n'
(
  cd "$ROOT_DIR"
  python -m src.imgprocessing.worker
) &
IMG_WORKER_PID=$!

printf 'Starting frontend on http://127.0.0.1:5173\n'
(
  cd "$FRONTEND_DIR"
  npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
) &
FRONTEND_PID=$!

wait -n "$BROKER_PID" "$HAYSTACK_PID" "$IMG_WORKER_PID" "$BACKEND_PID" "$FRONTEND_PID"
