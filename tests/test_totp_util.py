import time
from unittest.mock import patch

import pytest

from app.services.totp_util import get_fresh_totp_code, normalize_totp_secret


def test_normalize_strips_spaces_and_dashes():
    assert normalize_totp_secret(" jbsw y3dp-ehpk 3pxp ") == "JBSWY3DPEHPK3PXP"


def test_get_fresh_totp_code_length():
    # Well-known RFC test secret (base32)
    secret = "JBSWY3DPEHPK3PXP"
    code = get_fresh_totp_code(secret, min_seconds_left=0)
    assert code.isdigit()
    assert len(code) == 6


def test_get_fresh_totp_waits_near_window_end():
    secret = "JBSWY3DPEHPK3PXP"
    # Force almost end of 30s window
    fake_now = 1_000_000 * 30 + 28.0  # 2s left in window
    with patch("app.services.totp_util.time.time", return_value=fake_now):
        with patch("app.services.totp_util.time.sleep") as sleep_mock:
            with patch("pyotp.TOTP.now", return_value="123456"):
                code = get_fresh_totp_code(secret, min_seconds_left=5.0)
    assert code == "123456"
    sleep_mock.assert_called_once()
    assert sleep_mock.call_args[0][0] == pytest.approx(2.5, abs=0.2)


def test_invalid_secret_raises():
    with pytest.raises(RuntimeError, match="Invalid"):
        get_fresh_totp_code("!!!not-base32!!!")
