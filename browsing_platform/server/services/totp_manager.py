import base64
import io
import re
import secrets
from datetime import datetime, timezone
from typing import Optional

import pyotp
import qrcode

from browsing_platform.server.services.password_authenticator import _ph
from utils import db

BACKUP_CODE_COUNT = 8
TOTP_WINDOW = 1  # allow ±1 period (30s) for clock drift


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def generate_qr_code_png_b64(email: str, secret: str, issuer: str = "Magrefa") -> str:
    uri = pyotp.totp.TOTP(secret).provisioning_uri(email, issuer_name=issuer)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def verify_totp_code(secret: str, code: str, user_id: int) -> bool:
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=TOTP_WINDOW):
        return False

    # Replay prevention: reject if the same 30s epoch window was already used.
    # Use Unix timestamp arithmetic to align to the global 30s grid (not per-minute seconds).
    now_ts = datetime.now(timezone.utc).timestamp()
    window_start_ts = (now_ts // 30) * 30
    window_start_str = datetime.fromtimestamp(window_start_ts).strftime("%Y-%m-%d %H:%M:%S")

    row = db.execute_query(
        "SELECT totp_last_used_at FROM user WHERE id = %(uid)s",
        {"uid": user_id}, "single_row"
    )
    if row and row["totp_last_used_at"]:
        last_ts = row["totp_last_used_at"].timestamp()
        last_window_ts = (last_ts // 30) * 30
        if last_window_ts >= window_start_ts:
            return False  # same window already consumed

    db.execute_query(
        "UPDATE user SET totp_last_used_at = %(ts)s WHERE id = %(uid)s",
        {"ts": window_start_str, "uid": user_id}, "none"
    )
    return True


def generate_backup_codes() -> tuple[list[str], list[str]]:
    plaintext = [secrets.token_hex(4) for _ in range(BACKUP_CODE_COUNT)]
    hashes = [_ph.hash(code) for code in plaintext]
    return plaintext, hashes


def verify_and_consume_backup_code(user_id: int, provided_code: str) -> bool:
    rows = db.execute_query(
        "SELECT id, code_hash FROM totp_backup_code WHERE user_id = %(uid)s AND used = 0",
        {"uid": user_id}, "all_rows"
    )
    if not rows:
        return False

    matched_id = None
    for row in rows:
        try:
            _ph.verify(row["code_hash"], provided_code)
            matched_id = row["id"]
        except Exception:
            pass  # always check all codes to avoid timing leaks

    if matched_id is not None:
        db.execute_query(
            "UPDATE totp_backup_code SET used = 1 WHERE id = %(id)s",
            {"id": matched_id}, "none"
        )
        return True
    return False


def store_backup_codes(user_id: int, code_hashes: list[str]) -> None:
    db.execute_query(
        "DELETE FROM totp_backup_code WHERE user_id = %(uid)s",
        {"uid": user_id}, "none"
    )
    for h in code_hashes:
        db.execute_query(
            "INSERT INTO totp_backup_code (user_id, code_hash) VALUES (%(uid)s, %(h)s)",
            {"uid": user_id, "h": h}, "none"
        )


def get_totp_status(user_id: int) -> dict:
    user_row = db.execute_query(
        "SELECT totp_configured FROM user WHERE id = %(uid)s",
        {"uid": user_id}, "single_row"
    )
    count_row = db.execute_query(
        "SELECT COUNT(*) AS cnt FROM totp_backup_code WHERE user_id = %(uid)s AND used = 0",
        {"uid": user_id}, "single_row"
    )
    return {
        "configured": bool(user_row["totp_configured"]) if user_row else False,
        "backup_codes_remaining": count_row["cnt"] if count_row else 0,
    }
