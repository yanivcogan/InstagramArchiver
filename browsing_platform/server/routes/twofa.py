import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from browsing_platform.server.services.event_logger import log_event
from browsing_platform.server.services.permissions import auth_user_access, get_user_id
from browsing_platform.server.services.pre_auth_manager import (
    consume_pre_auth_token,
    create_pre_auth_token,
)
from browsing_platform.server.services.totp_manager import (
    generate_backup_codes,
    generate_qr_code_png_b64,
    generate_totp_secret,
    get_totp_status,
    store_backup_codes,
    verify_totp_code,
)
from browsing_platform.server.services.token_manager import generate_token
from utils import db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/2fa",
    tags=["2fa"],
    responses={404: {"description": "Not found"}},
)


class PreAuthRequest(BaseModel):
    pre_auth_token: str


class EnableRequest(BaseModel):
    pre_auth_token: str
    totp_code: str


class RegenerateRequest(BaseModel):
    totp_code: str


@router.post("/setup")
async def setup_totp(data: PreAuthRequest):
    """Step 1 of 2FA enrollment: generate a TOTP secret and return a QR code.
    Requires a valid pre_auth_token (issued after password verification)."""
    user_id = consume_pre_auth_token(data.pre_auth_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired setup token")

    user_row = db.execute_query("SELECT email FROM user WHERE id = %(uid)s", {"uid": user_id}, "single_row")
    if not user_row:
        raise HTTPException(status_code=401)

    secret = generate_totp_secret()
    db.execute_query(
        "UPDATE user SET totp_pending_secret = %(s)s WHERE id = %(uid)s",
        {"s": secret, "uid": user_id}, "none"
    )

    # Issue a new pre_auth_token so the enable step can proceed
    new_pre_auth = create_pre_auth_token(user_id)
    qr_code = generate_qr_code_png_b64(user_row["email"], secret)

    return {
        "qr_code": qr_code,
        "secret": secret,
        "pre_auth_token": new_pre_auth,
    }


@router.post("/enable")
async def enable_totp(data: EnableRequest):
    """Step 2 of 2FA enrollment: verify first TOTP code, activate 2FA, return backup codes + session token."""
    user_id = consume_pre_auth_token(data.pre_auth_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired setup token")

    user_row = db.execute_query(
        "SELECT totp_pending_secret, admin FROM user WHERE id = %(uid)s",
        {"uid": user_id}, "single_row"
    )
    if not user_row or not user_row["totp_pending_secret"]:
        raise HTTPException(status_code=409, detail="No pending 2FA setup found")

    pending_secret = user_row["totp_pending_secret"]
    if not verify_totp_code(pending_secret, data.totp_code, user_id):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    plaintext_codes, hashes = generate_backup_codes()
    store_backup_codes(user_id, hashes)

    db.execute_query(
        """UPDATE user
           SET totp_secret = %(s)s,
               totp_configured = 1,
               totp_method = 'totp',
               totp_pending_secret = NULL,
               force_pwd_reset = 0
           WHERE id = %(uid)s""",
        {"s": pending_secret, "uid": user_id}, "none"
    )

    token = generate_token()
    db.execute_query(
        "INSERT INTO token (user_id, token) VALUES (%(uid)s, %(tok)s)",
        {"uid": user_id, "tok": token}, "none"
    )
    log_event("2fa_attempt", user_id, json.dumps({"success": True, "step": "enrollment_complete"}), "{}")

    return {
        "backup_codes": plaintext_codes,
        "token": token,
        "permissions": bool(user_row["admin"]),
    }


@router.post("/backup-codes/regenerate")
async def regenerate_backup_codes(data: RegenerateRequest, request: Request, _=Depends(auth_user_access)):
    """Regenerate backup codes (authenticated endpoint). Requires a valid TOTP code."""
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401)

    user_row = db.execute_query(
        "SELECT totp_secret FROM user WHERE id = %(uid)s",
        {"uid": user_id}, "single_row"
    )
    if not user_row or not user_row["totp_secret"]:
        raise HTTPException(status_code=409, detail="2FA is not configured")

    if not verify_totp_code(user_row["totp_secret"], data.totp_code, user_id):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    plaintext_codes, hashes = generate_backup_codes()
    store_backup_codes(user_id, hashes)

    return {"backup_codes": plaintext_codes}


@router.get("/status")
async def totp_status(request: Request, _=Depends(auth_user_access)):
    """Return 2FA status for the current user."""
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401)
    return get_totp_status(user_id)
