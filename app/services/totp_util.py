# Fresh TOTP generation for MEGA 2FA (same idea as transfer.py).

from __future__ import annotations

import logging
import re
import time

logger = logging.getLogger(__name__)


def normalize_totp_secret(secret: str) -> str:
    # Strip whitespace and common separators; keep base32 alphabet chars.
    cleaned = re.sub(r"[\s\-]+", "", (secret or "").strip())
    return cleaned.upper()


def get_fresh_totp_code(secret: str, min_seconds_left: float = 5.0) -> str:
    """
    Return a TOTP code with at least ``min_seconds_left`` seconds of validity.

    If the current window is about to expire, wait for the next window so the
    code is not stale by the time MEGA processes login.
    Never log the secret or the code.
    """
    try:
        import pyotp
    except ImportError as exc:
        raise RuntimeError(
            "pyotp is required for MEGA TOTP auto-login. "
            "Install with: pip install pyotp"
        ) from exc

    cleaned = normalize_totp_secret(secret)
    if not cleaned:
        raise RuntimeError("TOTP secret is empty")

    try:
        totp = pyotp.TOTP(cleaned)
        # Validate secret early (invalid base32 raises)
        _ = totp.now()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Invalid MEGA TOTP secret. Use the base32 string from MEGA 2FA setup "
            "(not the 6-digit code)."
        ) from exc

    interval = float(totp.interval or 30)
    seconds_into_window = time.time() % interval
    seconds_left = interval - seconds_into_window

    if seconds_left < min_seconds_left:
        sleep_for = seconds_left + 0.5
        logger.info(
            "TOTP window nearly expired (%.1fs left); waiting %.1fs for a fresh code",
            seconds_left,
            sleep_for,
        )
        time.sleep(sleep_for)

    return totp.now()
