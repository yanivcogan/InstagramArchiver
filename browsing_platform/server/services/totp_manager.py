import base64
import io
from datetime import datetime, timezone

import pyotp
import qrcode
from pydantic import BaseModel

from utils import db


class TotpStatusResponse(BaseModel):
    configured: bool


TOTP_WINDOW = 1  # allow ±1 period (30s) for clock drift


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def generate_qr_code_png_b64(email: str, secret: str, issuer: str = "Evidence Platform") -> str:
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


def get_totp_status(user_id: int) -> TotpStatusResponse:
    row = db.execute_query(
        "SELECT totp_configured FROM user WHERE id = %(uid)s",
        {"uid": user_id}, "single_row"
    )
    return TotpStatusResponse(
        configured=bool(row["totp_configured"]) if row else False,
    )
