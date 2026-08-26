# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |

## Reporting a vulnerability

Do **not** open a public issue for security problems.

1. Prefer [GitHub Security Advisories](https://github.com/spellblade/Cloud-Copy/security/advisories) for this repository.
2. Or email **sohamray24@outlook.com** with:
   - Description of the issue
   - Steps to reproduce
   - Affected version (`VERSION` file or `/api/health`)

You should receive an acknowledgement when the report is seen. Please give a reasonable time to patch before public disclosure.

## What this app stores

Cloud Copy is a **local** transfer relay. Credentials and TOTP secrets are stored on the machine under `~/.cloud-copy/` (see [docs/security.md](docs/security.md)). Treat that directory like a password store.
