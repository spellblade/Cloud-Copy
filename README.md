# Cloud Copy — MEGA ↔ PikPak

Local web app that transfers files between **MEGA** and **PikPak** in both directions.

**Transfer model:** this is a **local relay**, not pure server-side cloud-to-cloud. Each file is downloaded from the source cloud to your PC (temp folder), then uploaded to the destination. It uses your bandwidth and disk. True MEGA↔PikPak server-side copy is not offered by either provider for private accounts.

## Features (v1)

- Connect MEGA and PikPak accounts
- Dual-pane file browser (source / destination)
- Transfer files and folders either direction
- Live progress over WebSocket
- Cancel and retry jobs
- Session restore from local credential store (`~/.cloud-copy/`)

## Requirements

- Python 3.11+
- Network access to MEGA and PikPak

## Install

`mega.py` pins an old `tenacity` that breaks on Python 3.11+. Use the install script (recommended):

```powershell
cd D:\cloud-copy
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
.\.venv\Scripts\Activate.ps1
```

Manual equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install fastapi "uvicorn[standard]" httpx pydantic pydantic-settings pikpakapi boto3 python-multipart requests pycryptodome "tenacity>=8.2.0"
pip install mega.py --no-deps
```

## Run

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**

Or:

```powershell
python -m app.main
```

## How to use

1. Sign in to **MEGA** and **PikPak** in the top panel.
2. Choose direction (**MEGA → PikPak** or reverse).
3. Browse the source pane; multi-select files/folders.
4. Navigate the destination pane to the target folder.
5. Click **Transfer selected**.
6. Watch progress in the **Transfers** section; cancel or retry as needed.

### MEGA with 2FA (recommended: TOTP secret)

6-digit codes expire in ~30 seconds and must not be saved. Cloud Copy can store your **TOTP secret** (the base32 string MEGA showed when you enabled 2FA — *not* the rotating code) and generate a **fresh** code at login time with `pyotp` (same idea as `transfer.py` for rclone).

1. When you set up MEGA 2FA, copy the base32 secret (or recover it from your authenticator export / QR). Keep it only on your PC.
2. In Cloud Copy: email, password, paste the secret into **TOTP secret (base32, recommended)** → **Connect**.
3. On success the secret is stored only in `~/.cloud-copy/credentials.json` on this machine. Restart auto-restores MEGA by minting a new code.
4. Optional: one-time 6-digit field still works as a one-shot override.
5. Optional env (never commit this):  
   `$env:MEGA_TOTP_SECRET = "YOUR_BASE32_SECRET"`  
   Then login with email/password; the app reads the secret from the environment.

You do **not** need to disable 2FA. Treat the TOTP secret like a password; logout clears the saved credentials.

Standalone rclone helper: `transfer.py` still works with `MEGA_TOTP_SECRET` + `--mega-2fa` if you prefer rclone outside this app.

## Architecture

| Piece | Role |
|---|---|
| FastAPI | Local HTTP + WebSocket API |
| `mega.py` | MEGA list / download / upload |
| `pikpakapi` + resumable upload | PikPak list / download / upload |
| Static UI | Dual-pane browser |

Data flow (local relay):

```
Source cloud  →  download to your PC  →  upload  →  Destination cloud
                 (~/.cloud-copy/temp/)
```

### Local paths (Windows)

| What | Default path |
|------|----------------|
| App data | `C:\Users\<you>\.cloud-copy\` |
| **Transfer temp** (downloads in transit) | `C:\Users\<you>\.cloud-copy\temp\` |
| Saved logins | `C:\Users\<you>\.cloud-copy\credentials.json` |

Each job uses a subfolder under `temp\` (UUID). Successful jobs are cleaned automatically; crashed/cancelled jobs can leave leftovers.

**Clear temp:**

- In the UI: **Clear temp** (Transfers section), or  
- API: `POST http://127.0.0.1:8000/api/system/clear-temp`  
- Paths info: `GET http://127.0.0.1:8000/api/system/paths`  
- Manual: delete everything inside `\.cloud-copy\temp\` (not while a transfer is mid-download).

## API (local)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/auth/status` | Connection status |
| POST | `/api/auth/mega` | Login MEGA `{username,password,totp_secret?,mfa_code?}` |
| POST | `/api/auth/pikpak` | Login PikPak |
| DELETE | `/api/auth/{provider}` | Logout |
| GET | `/api/files/{provider}?parent=` | List folder |
| POST | `/api/transfers` | Start transfer |
| GET | `/api/transfers` | List jobs |
| POST | `/api/transfers/{id}/cancel` | Cancel |
| POST | `/api/transfers/{id}/retry` | Retry |
| WS | `/ws/transfers` | Live job updates |

## Security notes

- Binds to **127.0.0.1** by default — not exposed to the network.
- Credentials are stored in `~/.cloud-copy/credentials.json` for session restore. Protect that folder on shared machines.
- MEGA decrypts on the client; plaintext passes through this app during transfer (inherent to any middle hop).

## Limits & caveats

- PikPak uses an **unofficial** API; it can change.
- PikPak uploads use temporary OSS credentials (FORM for smaller files, S3 resumable for larger, with fallback if storage returns AccessDenied).
- **Filenames on PikPak:** if the name is free, Cloud Copy keeps the exact source name (and renames back if PikPak spuriously adds `(1)`). If the name is already taken, a new copy is stored as `name(1).ext`, `name(2).ext`, … without overwriting.
- **MEGA free transfer quota:** downloading from MEGA counts against transfer limits (`EOVERQUOTA`). Wait for the window to reset or upgrade MEGA — this is not an app bug.
- Large libraries transfer sequentially (one job worker).
- Comply with each service’s terms of use.

## Development

```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## License

Personal / private use project. Third-party libraries retain their own licenses.
