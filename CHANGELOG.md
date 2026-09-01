# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

## [1.0.3] - 2026-09-01

### Added

### Changed

### Fixed

- Transfer progress bar and byte counts update during download/upload, not only when a file finishes (#4)

## [1.0.2] - 2026-08-31

### Added

- App version is shown next to the **Cloud Copy** title (from `/api/health`)

### Changed

- File-list **SIZE** column is nowrap with a fixed table layout so long names ellipsize instead of widening the pane (#9)

### Fixed

- File pane **Loading** is a centered overlay in the visible list (no scrolling to see it) (#9)
- Sticky **NAME** header stays above row icons while scrolling (`border-collapse: separate` + header `z-index`) (#9)
- PikPak (and MEGA) file lists no longer show a horizontal scrollbar; size stays on one line (`532.7 KB`) (#9)
- Hover a truncated filename to see the full name (`title` on the name span) (#9)
- Selecting a **folder** in the source pane queues a recursive copy (create dest folder, transfer children). Check the box to select; double-click still opens the folder (#5)

## [1.0.1] - 2026-08-17

### Added

- Linux/WSL install and run scripts (`scripts/install.sh`, `scripts/run.sh`)
- Dual-platform venv instructions in README (Windows and Linux are not interchangeable)
- `VERSION` as the documented source of truth (aligned with `app.__version__`)
- Failed transfer jobs show the stage (e.g. MEGA download vs PikPak upload)

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

## [0.0.1] - 2026-08-28

### Added

- Project documentation retrofit (`docs/`, GitHub issue/PR templates, CI workflow)
- Opened GitHub issues for the gist backlog (#1-#16) and recorded them in `docs/roadmap.md` with an implementation order (ease × risk × priority, resolved vs open, and feature branch names)

### Changed

### Fixed

[Unreleased]: https://github.com/spellblade/Cloud-Copy/compare/v1.0.3...HEAD
[1.0.3]: https://github.com/spellblade/Cloud-Copy/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/spellblade/Cloud-Copy/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/spellblade/Cloud-Copy/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/spellblade/Cloud-Copy/releases/tag/v1.0.0
[0.0.1]: https://github.com/spellblade/Cloud-Copy/releases/tag/v1.0.0
