import base64
import binascii
import hashlib
import hmac
import json
import time
from collections import deque
from threading import Lock

from fastapi import HTTPException

from app.config import get_settings

LOGIN_RATE_WINDOW_SECONDS = 900
LOGIN_RATE_LIMIT = 10
MAX_TRACKED_LOGIN_CLIENTS = 4096
_login_attempts: dict[str, deque[float]] = {}
_login_attempts_lock = Lock()


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def enforce_login_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    with _login_attempts_lock:
        attempts = _login_attempts.setdefault(client_ip, deque())
        while attempts and now - attempts[0] >= LOGIN_RATE_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= LOGIN_RATE_LIMIT:
            retry_after = max(1, int(LOGIN_RATE_WINDOW_SECONDS - (now - attempts[0])))
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts",
                headers={"Retry-After": str(retry_after)},
            )
        attempts.append(now)
        if len(_login_attempts) > MAX_TRACKED_LOGIN_CLIENTS:
            oldest_client = next(iter(_login_attempts))
            if oldest_client != client_ip:
                _login_attempts.pop(oldest_client, None)


def authenticate_admin(username: str, password: str) -> dict[str, int | str]:
    settings = get_settings()
    if (
        not settings.admin_username
        or not settings.admin_password
        or len(settings.admin_token_secret.encode("utf-8")) < 32
    ):
        raise HTTPException(status_code=503, detail="Admin authentication is not configured")

    if not hmac.compare_digest(username.encode("utf-8"), settings.admin_username.encode("utf-8")):
        raise _unauthorized()
    if not hmac.compare_digest(password.encode("utf-8"), settings.admin_password.encode("utf-8")):
        raise _unauthorized()

    expires_at = int(time.time()) + settings.admin_token_ttl_seconds
    payload = json.dumps(
        {"sub": settings.admin_username, "exp": expires_at},
        separators=(",", ":"),
    ).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(
        settings.admin_token_secret.encode("utf-8"),
        encoded_payload,
        hashlib.sha256,
    ).hexdigest()
    return {
        "access_token": f"{encoded_payload.decode('ascii')}.{signature}",
        "token_type": "bearer",
        "expires_in": settings.admin_token_ttl_seconds,
    }


def require_admin_token(authorization: str | None) -> None:
    settings = get_settings()
    if (
        not settings.admin_username
        or not settings.admin_password
        or len(settings.admin_token_secret.encode("utf-8")) < 32
    ):
        raise HTTPException(status_code=503, detail="Admin authentication is not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized()

    token = authorization[7:].strip()
    if token.count(".") != 1:
        raise _unauthorized()
    encoded_payload, supplied_signature = token.split(".", 1)
    if not encoded_payload or len(supplied_signature) != 64:
        raise _unauthorized()

    try:
        encoded_payload_bytes = encoded_payload.encode("ascii")
        supplied_signature_bytes = bytes.fromhex(supplied_signature)
    except (UnicodeEncodeError, ValueError):
        raise _unauthorized() from None
    expected_signature = hmac.new(
        settings.admin_token_secret.encode("utf-8"),
        encoded_payload_bytes,
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(supplied_signature_bytes, expected_signature):
        raise _unauthorized()

    try:
        padded_payload = encoded_payload + "=" * (-len(encoded_payload) % 4)
        payload_bytes = base64.b64decode(padded_payload, altchars=b"-_", validate=True)
        payload = json.loads(payload_bytes)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error):
        raise _unauthorized() from None

    if (
        not isinstance(payload, dict)
        or payload.get("sub") != settings.admin_username
        or type(payload.get("exp")) is not int
        or payload["exp"] <= int(time.time())
    ):
        raise _unauthorized()


def require_device_key(header_value: str | None) -> None:
    settings = get_settings()
    if not settings.device_key or not header_value:
        raise HTTPException(status_code=401, detail="Invalid device key")
    if not hmac.compare_digest(header_value.encode("utf-8"), settings.device_key.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid device key")
