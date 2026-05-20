#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/src/web"

if ! command -v npm >/dev/null 2>&1; then
  printf 'Missing npm. Install Node.js and npm first.\n' >&2
  exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  printf 'Installing frontend dependencies...\n'
  npm install --prefix "$FRONTEND_DIR"
fi

printf 'Starting frontend on http://127.0.0.1:5173\n'
cd "$FRONTEND_DIR"
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
