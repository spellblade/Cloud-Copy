# Install Cloud Copy dependencies (handles mega.py / tenacity conflict on Python 3.11+)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\pip.exe install fastapi "uvicorn[standard]" httpx pydantic pydantic-settings pikpakapi boto3 python-multipart requests pycryptodome "tenacity>=8.2.0" pyotp
.\.venv\Scripts\pip.exe install mega.py --no-deps

Write-Host "Done. Activate with: .\.venv\Scripts\Activate.ps1"
Write-Host "Run with: uvicorn app.main:app --host 127.0.0.1 --port 8000"
