# Setup

## Prerequisites

- Python 3.11 or newer (`python3` on Linux/WSL)
- Network access to MEGA and PikPak

## Virtualenv

`.venv/` is **gitignored**. Create a new venv on **each** machine and OS.

Do **not** copy a Windows `.venv` into Linux/WSL (or the reverse).

`mega.py` pins an old `tenacity`. Install other packages first, then:

```bash
pip install mega.py --no-deps
```

The install scripts do this.

### Windows (PowerShell)

```powershell
cd <clone>
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
.\.venv\Scripts\Activate.ps1
```

### Linux / WSL (bash)

```bash
cd ~/projects/cloud-copy   # or your clone path
bash scripts/install.sh
source .venv/bin/activate
```

### Manual (same packages)

See the README “Virtual environment” section.

## Run

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Windows: `.\scripts\run.ps1`  
Linux: `bash scripts/run.sh`

Open http://127.0.0.1:8000

## Tests

```bash
pip install -r requirements-dev.txt   # if not already
python -m pytest
```

Use `python -m pytest` so the project root is on `sys.path` (`import app`). Bare `pytest` often fails with `No module named 'app'`.
