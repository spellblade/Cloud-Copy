# Architecture

## Transfer model

Neither MEGA nor PikPak offers a private-account “copy from the other cloud” API. Cloud Copy runs a **local relay**:

```
Source cloud  →  download to this PC  →  upload  →  Destination cloud
                 (~/.cloud-copy/temp/<job-id>/)
```

MEGA decrypts on the client; plaintext exists on disk (and in memory) during the hop.

## Package layout

This project uses **`app/`**, not `src/`. That matches FastAPI’s usual package name and existing imports (`app.main:app`). Do not move to `src/` without a dedicated refactor.

```
app/
  main.py              FastAPI app, static UI, lifespan (session restore)
  config.py            Data/temp dirs under ~/.cloud-copy
  models.py            Pydantic API models
  routers/             auth, files, transfers, system
  services/
    mega_client.py     MEGA adapter (mega.py + Windows-safe download)
    pikpak_client.py   PikPak adapter (pikpakapi + FORM/S3 upload)
    totp_util.py       Fresh TOTP from stored secret
    transfer_service.py Job queue, worker, cancel
    credential_store.py Local JSON credentials
  static/              Dual-pane UI
tests/
scripts/               install/run for Windows and Linux
```

## Runtime flow

```
Browser UI  ←HTTP/WS→  FastAPI
                         ├── /api/auth
                         ├── /api/files
                         ├── /api/transfers + /ws/transfers
                         └── TransferService
                               ├── MegaAdapter
                               └── PikPakAdapter
```

Jobs run **sequentially** (one worker) to stay kinder to API rate limits.

## Version

`VERSION` is the source of truth. Keep `app/__init__.py` `__version__` in sync.
