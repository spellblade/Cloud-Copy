#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -x .venv/bin/uvicorn ]]; then
  echo "Virtualenv missing or incomplete. Run: bash scripts/install.sh" >&2
  exit 1
fi

exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
