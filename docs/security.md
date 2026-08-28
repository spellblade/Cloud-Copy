# Security notes

## Bind address

The server binds to **127.0.0.1** by default. Do not expose it to the network without authentication.

## Secrets on disk

| Path | Contents |
|------|----------|
| `~/.cloud-copy/credentials.json` | MEGA email/password, optional TOTP secret; PikPak tokens |
| `~/.cloud-copy/temp/` | File contents in transit (plaintext after MEGA decrypt) |

The documentation template recommends OS **keyring** and no plaintext secrets. This app **does not** use keyring yet. Protect `~/.cloud-copy/` on shared machines. Logout deletes stored provider credentials.

## Transfers

- All cloud APIs over HTTPS.
- MEGA plaintext exists on this machine during relay — inherent to any middle hop.
- Integrity: PikPak gcid; MEGA MAC check on download. There is no end-to-end SHA-256 compare between clouds yet.

## Git

`.gitignore` excludes `.venv/`, `.env`, and `credentials`-style paths. Never commit TOTP secrets or `credentials.json`.
