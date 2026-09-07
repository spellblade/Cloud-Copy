import ssl

import httpx

from app.services.pikpak_client import is_retryable_pikpak_upload_error


def test_ssl_eof_is_retryable():
    assert is_retryable_pikpak_upload_error(ssl.SSLError("EOF occurred in violation of protocol"))
    assert is_retryable_pikpak_upload_error(
        RuntimeError(
            "SSL validation failed for https://upload-a10b.mypikpak.com/x "
            "EOF occurred in violation of protocol (_ssl.c:2406)"
        )
    )
    assert is_retryable_pikpak_upload_error(httpx.RemoteProtocolError("peer closed"))
    assert is_retryable_pikpak_upload_error(httpx.ConnectError("connection reset"))
    try:
        from botocore.exceptions import SSLError as BotoSSLError

        assert is_retryable_pikpak_upload_error(
            BotoSSLError(error=ssl.SSLError("EOF"), endpoint_url="https://upload-a10b.mypikpak.com/x")
        )
    except TypeError:
        pass


def test_access_denied_is_not_retryable():
    assert not is_retryable_pikpak_upload_error(
        RuntimeError("AccessDenied when calling PutObject: denied")
    )
    assert not is_retryable_pikpak_upload_error(
        RuntimeError("PikPak FORM upload failed HTTP 403: forbidden")
    )
