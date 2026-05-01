"""
Stateless signed tokens for password-protected share links.

A token encodes `{link_suffix}:{expiry_unix_ts}` and is authenticated with
HMAC-SHA256 keyed on the FILE_TOKEN_SECRET.  Tokens expire after 24 hours.
No database state is required.
"""

import base64
import hashlib
import hmac
import time
from typing import Optional

from browsing_platform.server.services.file_tokens import _get_secret as _load_secret

_TOKEN_TTL = 86_400  # 24 hours

_SECRET: Optional[bytes] = None


def _secret() -> bytes:
    global _SECRET
    if _SECRET is None:
        _SECRET = _load_secret()
    return _SECRET


def _sign(message: str) -> str:
    sig = hmac.digest(_secret(), message.encode(), hashlib.sha256)
    return base64.urlsafe_b64encode(sig).rstrip(b"=").decode()


def generate_password_token(link_suffix: str) -> str:
    expiry = int(time.time()) + _TOKEN_TTL
    message = f"{link_suffix}:{expiry}"
    sig = _sign(message)
    payload = f"{message}:{sig}"
    return base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()


def validate_password_token(link_suffix: str, token: str) -> bool:
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = base64.urlsafe_b64decode(padded).decode()
        parts = payload.rsplit(":", 2)
        if len(parts) != 3:
            return False
        suffix_part, expiry_str, provided_sig = parts
        if suffix_part != link_suffix:
            return False
        if int(expiry_str) < int(time.time()):
            return False
        expected_sig = _sign(f"{suffix_part}:{expiry_str}")
        return hmac.compare_digest(provided_sig, expected_sig)
    except Exception:
        return False
