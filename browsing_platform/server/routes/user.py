import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from browsing_platform.server.services.event_logger import log_event
from browsing_platform.server.services.password_authenticator import (
    hash_password,
    verify_password,
)
from browsing_platform.server.services.permissions import auth_user_access, get_user_id
from browsing_platform.server.services.pre_auth_manager import (
    consume_pre_auth_token,
    create_pre_auth_token,
)
from browsing_platform.server.services.totp_manager import get_totp_status, verify_totp_code
from browsing_platform.server.services.token_manager import generate_token, remove_all_tokens_for_user
from utils import db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={404: {"description": "Not found"}},
)


class ChangePasswordPreAuth(BaseModel):
    """Used for forced first-time password change (no existing session token)."""
    pre_auth_token: str
    new_password: str


class ChangePasswordVoluntary(BaseModel):
    """Used from SecuritySettings (user already has a valid session)."""
    current_password: str
    new_password: str
    totp_code: str


@router.post("/change-password/preauth")
async def change_password_preauth(data: ChangePasswordPreAuth):
    """Force password change for new/reset accounts. Uses a pre_auth_token instead of session."""
    user_id = consume_pre_auth_token(data.pre_auth_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        new_hash, alg = hash_password(data.new_password)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    remove_all_tokens_for_user(user_id)
    db.execute_query(
        """UPDATE user
           SET password_hash = %(h)s,
               password_alg = %(alg)s,
               password_set_at = NOW(),
               login_attempts = 0,
               force_pwd_reset = 0
           WHERE id = %(uid)s""",
        {"h": new_hash, "alg": alg, "uid": user_id}, "none"
    )
    log_event("password_change", user_id, json.dumps({"method": "preauth"}), "{}")

    # Check whether 2FA still needs to be set up
    user_row = db.execute_query(
        "SELECT totp_configured, admin FROM user WHERE id = %(uid)s",
        {"uid": user_id}, "single_row"
    )
    if not user_row or not user_row["totp_configured"]:
        new_pre_auth = create_pre_auth_token(user_id)
        return {"next_step": "setup_totp", "pre_auth_token": new_pre_auth}

    # 2FA already configured — issue session token
    token = generate_token()
    db.execute_query(
        "INSERT INTO token (user_id, token) VALUES (%(uid)s, %(tok)s)",
        {"uid": user_id, "tok": token}, "none"
    )
    return {"token": token, "permissions": bool(user_row["admin"])}


@router.post("/change-password")
async def change_password(data: ChangePasswordVoluntary, request: Request, _=Depends(auth_user_access)):
    """Voluntary password change from SecuritySettings. Requires current password + TOTP."""
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401)

    user_row = db.execute_query(
        "SELECT password_hash, totp_secret, admin FROM user WHERE id = %(uid)s",
        {"uid": user_id}, "single_row"
    )
    if not user_row:
        raise HTTPException(status_code=401)

    ok = verify_password(user_row["password_hash"], data.current_password)
    if not ok:
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    if not user_row["totp_secret"] or not verify_totp_code(user_row["totp_secret"], data.totp_code, user_id):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    try:
        new_hash, alg = hash_password(data.new_password)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    remove_all_tokens_for_user(user_id)
    db.execute_query(
        """UPDATE user
           SET password_hash = %(h)s,
               password_alg = %(alg)s,
               password_set_at = NOW(),
               login_attempts = 0
           WHERE id = %(uid)s""",
        {"h": new_hash, "alg": alg, "uid": user_id}, "none"
    )
    log_event("password_change", user_id, json.dumps({"method": "voluntary"}), "{}")

    # Issue a fresh session token so the caller stays logged in
    new_token = generate_token()
    db.execute_query(
        "INSERT INTO token (user_id, token) VALUES (%(uid)s, %(tok)s)",
        {"uid": user_id, "tok": new_token}, "none"
    )
    return {"token": new_token, "permissions": bool(user_row["admin"])}


@router.get("/security-status")
async def security_status(request: Request, _=Depends(auth_user_access)):
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401)
    return get_totp_status(user_id)
