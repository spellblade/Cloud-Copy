$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .\.venv\Scripts\uvicorn.exe)) {
    Write-Host "Virtualenv missing. Run scripts\install.ps1 first."
    exit 1
}
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
