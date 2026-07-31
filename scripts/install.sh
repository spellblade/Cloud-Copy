#!/usr/bin/env bash
# Install Cloud Copy dependencies (handles mega.py / tenacity conflict on Python 3.11+)
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -U pip
pip install fastapi "uvicorn[standard]" httpx pydantic pydantic-settings \
  pikpakapi boto3 python-multipart requests pycryptodome "tenacity>=8.2.0" pyotp
# mega.py pins an old tenacity; install without resolving that pin
pip install mega.py --no-deps

echo "Done. Activate with: source .venv/bin/activate"
echo "Run with: uvicorn app.main:app --host 127.0.0.1 --port 8000"
