# Providers

Cloud Copy currently implements **two** providers. Template 02’s GDrive/Dropbox/S3/Azure/OneDrive list is **not** in this product.

| Provider | Client | Notes |
|----------|--------|--------|
| MEGA | `mega.py` (custom login + download) | E2E encryption; MFA via `mfa` on login; TOTP helper |
| PikPak | `pikpakapi` + custom upload | Unofficial API; FORM for smaller files; S3 resumable with checksums disabled |

## MEGA

- Login: password + optional TOTP secret or one-shot code.
- Download: custom path (avoids `mega.py` `NamedTemporaryFile` + `shutil.move` on Windows, WinError 32).
- Quota: free accounts hit transfer limits (`EOVERQUOTA`).
- Pane delete: `mega.py` `delete(node_id)` moves the folder to Rubbish (type 4). Not `destroy`.

## PikPak

- Login: email/phone + password; tokens persisted locally.
- Upload: gcid hash; FORM POST or Aliyun-compatible PutObject; AccessDenied → FORM fallback.
- Incomplete uploads: best-effort `delete_forever` of file/task.
- Pane delete: `delete_to_trash` (not `delete_forever`).

## Adding a provider later

Mirror `MegaAdapter` / `PikPakAdapter`: `login`, `list_folder`, `download_to_path`, `upload_from_path`, `mkdir`, `delete_folder`. Wire `TransferService` directions explicitly. Do not assume a generic URI scheme exists yet.
