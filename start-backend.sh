#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  echo "Python environment is missing. Run: python3 -m venv .venv && .venv/bin/pip install -e '.[test]'"
  exit 1
fi
if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Backend is already running on http://127.0.0.1:8000"
  exit 0
fi
cd "$PROJECT_DIR"
exec "$PROJECT_DIR/.venv/bin/python" -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
