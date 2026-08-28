# Contributing

Thank you for helping improve Cloud Copy.

## Branches

- **`master`** — default branch; keep it stable.
- **`temp/*`** — experiments and retrofits (for example `temp/retrofit-structure`). Do not assume these are merge-ready.
- Optional **`develop`** — integration branch if you adopt a two-branch model later.

Open pull requests against `master` unless a maintainer says otherwise.

## Setup

Follow [docs/setup.md](docs/setup.md). Summary:

- Python 3.11+
- Create a **new** `.venv` on this OS (gitignored; Windows and Linux venvs are not interchangeable)
- Use `scripts/install.ps1` (Windows) or `scripts/install.sh` (Linux/WSL)

## Tests

```bash
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
python -m pytest
```

Use `python -m pytest` so `app` is importable (CI uses the same command).

Install `mega.py` with `--no-deps` after other packages (see setup docs). A plain `pip install -r requirements.txt` may fail on the `tenacity` pin.

## Commit messages

Prefer short, prefixed messages:

- `feat:` user-facing behavior
- `fix:` bug fix
- `docs:` documentation only
- `chore:` tooling, venv, ignore files
- `ci:` GitHub Actions / templates
- `refactor:` no intended behavior change

## Code style

See [docs/coding-standards.md](docs/coding-standards.md). This repo uses the `app/` package (not `src/`).

## Pull requests

Use the PR template. Include:

- What changed and why
- How you tested (pytest / manual transfer)
- Any MEGA/PikPak API caveats
