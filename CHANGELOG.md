# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Project documentation retrofit (`docs/`, GitHub issue/PR templates, CI workflow)

### Changed

### Fixed

## [1.0.1] - 2026-08-17

### Added

- Linux/WSL install and run scripts (`scripts/install.sh`, `scripts/run.sh`)
- Dual-platform venv instructions in README (Windows and Linux are not interchangeable)
- `VERSION` as the documented source of truth (aligned with `app.__version__`)

### Changed

### Fixed

- App version in `app/__init__.py` was still `0.1.0` while README said `1.0.0`
- CI runs `python -m pytest` so the `app` package is importable (bare `pytest` failed with `No module named 'app'`)
- Transfer job timestamps use timezone-aware UTC (`datetime.now(timezone.utc)`) instead of deprecated `utcnow()`

## [1.0.0] - 2026-07-31

### Added

- Local web app for MEGA ↔ PikPak file transfer (FastAPI + dual-pane UI)
- MEGA 2FA via TOTP secret (`pyotp`) or one-shot code
- Windows-safe MEGA download path
- PikPak FORM/S3 upload with AccessDenied fallback
- Filename preservation on PikPak (rename-back; `(n)` suffix if name is taken)
- Transfer cancel, retry, and temp-folder clear
- Clearer MEGA `EOVERQUOTA` messages

### Changed

### Fixed

[Unreleased]: https://github.com/spellblade/Cloud-Copy/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/spellblade/Cloud-Copy/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/spellblade/Cloud-Copy/releases/tag/v1.0.0
