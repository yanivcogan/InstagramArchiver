from datetime import datetime, timedelta
from typing import Literal, Optional

from browsing_platform.server.services.token_manager import generate_token
from utils import db

PRE_AUTH_TOKEN_LENGTH = 48
PRE_AUTH_TTL_SECONDS = 300  # 5 minutes

PreAuthPurpose = Literal["change_password", "setup_totp", "setup_totp_enable", "verify_totp"]


def create_pre_auth_token(user_id: int, purpose: PreAuthPurpose) -> str:
    token = generate_token(PRE_AUTH_TOKEN_LENGTH)
    expires_at = (datetime.now() + timedelta(seconds=PRE_AUTH_TTL_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute_query(
        "INSERT INTO pre_auth_token (user_id, token, expires_at, purpose) "
        "VALUES (%(uid)s, %(tok)s, %(exp)s, %(p)s)",
        {"uid": user_id, "tok": token, "exp": expires_at, "p": purpose}, "none"
    )
    return token


def consume_pre_auth_token(token: str, expected_purpose: PreAuthPurpose) -> Optional[int]:
    row = db.execute_query(
        "SELECT id, user_id FROM pre_auth_token "
        "WHERE token = %(tok)s AND purpose = %(p)s AND expires_at > NOW()",
        {"tok": token, "p": expected_purpose}, "single_row"
    )
    if not row:
        return None
    db.execute_query(
        "DELETE FROM pre_auth_token WHERE id = %(id)s",
        {"id": row["id"]}, "none"
    )
    return row["user_id"]


def cleanup_expired_pre_auth_tokens() -> None:
    db.execute_query(
        "DELETE FROM pre_auth_token WHERE expires_at < NOW()",
        {}, "none"
    )
