# Coding standards

- **Python 3.11+**; use `str | None` union syntax.
- Type hints on public functions and Pydantic models.
- **Files / functions:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE`
- Package name is **`app`**, not `src`.

## Errors

- Prefer specific exceptions (`RuntimeError` with a user-facing message, HTTP 4xx from routers).
- Broad `except Exception` exists in adapters (unofficial APIs). When adding new code, catch narrower types where you can; do not silently swallow errors.
- MEGA numeric codes are mapped in `mega_client._map_mega_error`.

## Logging

- Never log TOTP secrets, 6-digit codes, passwords, or OSS access keys.
- Log upload method (`FORM` vs `S3`) and non-secret metadata only.

## Tests

- Unit tests live in `tests/` and must not hit live MEGA/PikPak.
- Manual QA with real accounts is required for transfers.

## Format

`.editorconfig`: UTF-8, LF, 4-space indent for Python, 2-space for YAML/JSON/Markdown.
