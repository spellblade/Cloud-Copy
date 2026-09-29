# Security notes

## Bind address

The server binds to **127.0.0.1** by default. Do not expose it to the network without authentication.

`POST /api/auth/mega` and `POST /api/auth/pikpak` allow 10 attempts per IP per 60 seconds (429 with `Retry-After` after that). Status and logout are not limited.

## Secrets on disk

| Path | Contents |
|------|----------|
| `~/.cloud-copy/credentials.json` | MEGA email/password, optional TOTP secret; PikPak tokens |
| `~/.cloud-copy/temp/` | File contents in transit (plaintext after MEGA decrypt) |

The documentation template recommends OS **keyring** and no plaintext secrets. This app **does not** use keyring yet. Credentials stay in that JSON file.

On **POSIX** (Linux/macOS), Cloud Copy creates `~/.cloud-copy/` as `0700` and `credentials.json` as `0600`, and writes the file atomically (temp file + replace). Existing installs are chmod'd on the next start.

On **Windows**, `os.chmod` does not keep other local accounts out of the file. Protect the profile directory on shared machines. Logout deletes stored provider credentials.

## Transfers

- All cloud APIs over HTTPS.
- MEGA plaintext exists on this machine during relay — inherent to any middle hop.
- Integrity: PikPak gcid; MEGA MAC check on download. MEGA uploads set the official fingerprint attribute (``c``) so MEGA Desktop does not treat the file as corrupted. There is no end-to-end SHA-256 compare between clouds yet.

## Git

`.gitignore` excludes `.venv/`, `.env`, and `credentials`-style paths. Never commit TOTP secrets or `credentials.json`.
