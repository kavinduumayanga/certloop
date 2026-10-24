#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -d "$PROJECT_DIR/frontend/node_modules" ]]; then
  echo "Frontend dependencies are missing. Run: cd frontend && npm install"
  exit 1
fi
if lsof -nP -iTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Frontend is already running on http://127.0.0.1:5173"
  exit 0
fi
cd "$PROJECT_DIR/frontend"
exec npm run dev -- --host 127.0.0.1

