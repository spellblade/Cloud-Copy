import requests

from app.services.mega_client import (
    is_retryable_mega_download_error,
    prefer_https_storage_url,
)


def test_prefer_https_rewrites_port_80_storage_url():
    http = "http://gfs270n339.userstorage.mega.co.nz/dl/abc"
    https = prefer_https_storage_url(http)
    assert https.startswith("https://")
    assert "gfs270n339.userstorage.mega.co.nz" in https
    assert prefer_https_storage_url(https) == https


def test_prefer_https_leaves_other_schemes():
    assert prefer_https_storage_url("https://example/x") == "https://example/x"
    assert prefer_https_storage_url("/relative") == "/relative"


def test_read_timeout_is_retryable():
    assert is_retryable_mega_download_error(requests.exceptions.ReadTimeout())
    assert is_retryable_mega_download_error(requests.exceptions.ConnectTimeout())
    assert is_retryable_mega_download_error(requests.exceptions.ConnectionError())
    assert not is_retryable_mega_download_error(ValueError("MAC mismatch"))
    assert not is_retryable_mega_download_error(RuntimeError("quota"))
