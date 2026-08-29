# Usage

1. Sign in to **MEGA** and **PikPak** in the top panel.
2. Choose direction (MEGA → PikPak or reverse).
3. Browse the source pane; select files or folders.
4. Open the destination folder on the right.
5. Click **Transfer selected**.
6. Watch **Transfers**; cancel or retry as needed.

## MEGA 2FA

Prefer the **TOTP secret** (base32 from MEGA 2FA setup), not a 6-digit code.

- Stored only in `~/.cloud-copy/credentials.json` on this machine.
- The app mints a fresh code at login (waits if the 30s window is about to expire).
- Optional env: `MEGA_TOTP_SECRET` (never commit this).
- Optional one-shot 6-digit field still works. Use it only with a **newly generated** code that still has time left (about 30 seconds per code). The login form warns about this.

You do not need to disable 2FA.

## Filenames on PikPak

- If the name is free: keep the source name; if PikPak adds a spurious `(1)`, Cloud Copy renames back.
- If the name is taken: upload as `name(1).ext`, then `(2)`, … — no overwrite.
- Some files may still be renamed by PikPak itself (their web/app does the same). That is not fixable here.

## Cancel

Cancel updates the job immediately. A download or upload already in a worker thread finishes the current step, then the job stops (it is not a hard kill of the OS process).

## Temp files

Relay files live under `~/.cloud-copy/temp/` (Windows: `C:\Users\<you>\.cloud-copy\temp\`).

- UI: **Clear temp**
- `GET /api/system/paths`
- `POST /api/system/clear-temp`

Do not clear temp while a transfer is mid-download.

## MEGA quota

`EOVERQUOTA` is MEGA’s **free transfer quota** (downloads), not an application bug. Wait for the window to reset or upgrade MEGA.
