#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
children=()
cleanup() { for pid in "${children[@]:-}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

if ! lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  "$PROJECT_DIR/start-backend.sh" & children+=("$!")
else
  echo "Backend already running on http://127.0.0.1:8000"
fi
if ! lsof -nP -iTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
  "$PROJECT_DIR/start-frontend.sh" & children+=("$!")
else
  echo "Frontend already running on http://127.0.0.1:5173"
fi

echo "Certificate Dispatch: http://127.0.0.1:5173"
if ((${#children[@]})); then wait "${children[@]}"; fi
