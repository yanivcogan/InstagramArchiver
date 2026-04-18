import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from browsing_platform.server.services.password_authenticator import set_user_password
from browsing_platform.server.services.permissions import auth_admin_access
from browsing_platform.server.services.token_manager import remove_all_tokens_for_user
from browsing_platform.server.services.user_manager import delete_user as _delete_user
from utils import db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/users",
    tags=["admin"],
    dependencies=[Depends(auth_admin_access)],
    responses={404: {"description": "Not found"}},
)


class CreateUserRequest(BaseModel):
    email: str
    admin: bool = False
    temp_password: str


class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    admin: Optional[bool] = None
    locked: Optional[bool] = None
    force_pwd_reset: Optional[bool] = None
    temp_password: Optional[str] = None


class AdminUserRow(BaseModel):
    id: int
    email: str
    admin: bool
    locked: bool
    totp_configured: bool
    force_pwd_reset: bool
    last_login: Optional[datetime]
    login_attempts: int
    create_date: Optional[datetime]


class CreatedUserResponse(BaseModel):
    id: int
    email: str


@router.get("/")
async def list_users() -> list[AdminUserRow]:
    rows = db.execute_query(
        """SELECT id, email, admin, locked, last_login, login_attempts,
                  totp_configured, force_pwd_reset, create_date
           FROM user ORDER BY id""",
        {}, "rows"
    )
    return [AdminUserRow(**row) for row in rows] if rows else []


@router.post("/")
async def create_user(data: CreateUserRequest) -> CreatedUserResponse:
    existing = db.execute_query(
        "SELECT id FROM user WHERE email = %(e)s", {"e": data.email}, "single_row"
    )
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use")

    new_id = db.execute_query(
        "INSERT INTO user (email, admin, locked, force_pwd_reset) VALUES (%(e)s, %(a)s, 0, 1)",
        {"e": data.email, "a": int(data.admin)}, "id"
    )
    try:
        set_user_password(new_id, data.temp_password)
    except ValueError as e:
        db.execute_query("DELETE FROM user WHERE id = %(id)s", {"id": new_id}, "none")
        raise HTTPException(status_code=422, detail=str(e))

    return CreatedUserResponse(id=new_id, email=data.email)


@router.patch("/{user_id}")
async def update_user(user_id: int, data: UpdateUserRequest) -> Any:
    user_row = db.execute_query(
        "SELECT id, locked FROM user WHERE id = %(uid)s", {"uid": user_id}, "single_row"
    )
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    updates = {}
    if data.email is not None:
        updates["email"] = data.email
    if data.admin is not None:
        updates["admin"] = int(data.admin)
    if data.locked is not None:
        updates["locked"] = int(data.locked)
    if data.force_pwd_reset is not None:
        updates["force_pwd_reset"] = int(data.force_pwd_reset)

    if updates:
        set_clause = ", ".join(f"{k} = %({k})s" for k in updates)
        updates["uid"] = user_id
        db.execute_query(f"UPDATE user SET {set_clause} WHERE id = %(uid)s", updates, "none")

    if data.locked:
        remove_all_tokens_for_user(user_id)

    if data.temp_password:
        try:
            set_user_password(user_id, data.temp_password)
            db.execute_query(
                "UPDATE user SET force_pwd_reset = 1 WHERE id = %(uid)s",
                {"uid": user_id}, "none"
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    return {"success": True}


@router.delete("/{user_id}")
async def delete_user(user_id: int) -> Any:
    user_row = db.execute_query(
        "SELECT id FROM user WHERE id = %(uid)s", {"uid": user_id}, "single_row"
    )
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    _delete_user(user_id)
    return {"success": True}


@router.post("/{user_id}/reset-2fa")
async def reset_2fa(user_id: int) -> Any:
    user_row = db.execute_query(
        "SELECT id FROM user WHERE id = %(uid)s", {"uid": user_id}, "single_row"
    )
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    db.execute_query(
        """UPDATE user
           SET totp_configured = 0,
               totp_secret = NULL,
               totp_pending_secret = NULL,
               totp_last_used_at = NULL
           WHERE id = %(uid)s""",
        {"uid": user_id}, "none"
    )
    remove_all_tokens_for_user(user_id)

    return {"success": True}
