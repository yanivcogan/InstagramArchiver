import json
import logging
import os
from typing import Optional

from fastapi import HTTPException
from starlette.requests import Request

from browsing_platform.server.services.entities_hierarchy import T_Entities
from browsing_platform.server.services.event_logger import log_event
from browsing_platform.server.services.sharing_manager import check_share_permissions, \
    SharePermissions
from browsing_platform.server.services.token_manager import check_token, TokenPermissions
from utils import db

logger = logging.getLogger(__name__)


def parse_token_from_header(auth_header: Optional[str]) -> Optional[str]:
    """Safely parse token from Authorization header. Expected format: 'token:xxx'"""
    if not auth_header:
        return None
    parts = auth_header.split(":", 1)
    if len(parts) != 2 or parts[0] != "token":
        return None
    return parts[1] if parts[1] else None


async def get_auth_permissions(request: Request):
    auth_header = request.headers.get("Authorization")
    token = parse_token_from_header(auth_header)
    if not token:
        return None
    return check_token(token)


async def _log_body_snippet(request: Request) -> str:
    """Return a short excerpt of the request body for diagnostic logging.
    Skips reading entirely for non-JSON content types to avoid buffering large
    binary payloads (e.g. TUS file chunks) and to prevent UnicodeDecodeError."""
    if "application/json" not in request.headers.get("content-type", ""):
        return "<non-json body skipped>"
    try:
        body = await request.body()
        return body[:512].decode("utf-8", errors="replace")
    except Exception:
        return "<unreadable>"


async def raise_auth_user_error(request: Request, token_permissions: Optional[TokenPermissions]):
    if not token_permissions:
        body_snippet = await _log_body_snippet(request)
        logger.warning(f"Unauthorized access - missing or invalid auth header: {request.scope['route'].path}")
        log_event("unauthorized_access", None,
                  request.scope['root_path'] + request.scope['route'].path,
                  json.dumps({"body": body_snippet}))
        raise HTTPException(status_code=401)
    elif not token_permissions.valid:
        body_snippet = await _log_body_snippet(request)
        logger.warning(f"Unauthorized access - invalid token: {request.scope['route'].path}")
        log_event("unauthorized_access", None,
                  request.scope['root_path'] + request.scope['route'].path,
                  json.dumps({"body": body_snippet}))
        raise HTTPException(status_code=401)
    else:
        logger.debug(f"Auth successful for user {token_permissions.user_id}: {request.scope['route'].path}")
        return True


async def auth_user_access(request: Request):
    """verify that user has a valid session"""
    # Bypass auth in dev mode (only when explicitly set to "1")
    if os.getenv("BROWSING_PLATFORM_DEV") == "1":
        logger.debug("Auth bypassed - dev mode enabled")
        return True
    token_permissions = await get_auth_permissions(request)
    return await raise_auth_user_error(request, token_permissions)


async def get_share_permissions(request: Request) -> Optional[str]:
    return request.headers.get("X-Share-Link")


async def raise_share_access_error(request: Request, share_permissions: Optional[SharePermissions]):
    if not share_permissions:
        body_snippet = await _log_body_snippet(request)
        logger.warning(f"Unauthorized access - missing or invalid share token: {request.scope['route'].path}")
        log_event("unauthorized_access", None,
                  request.scope['root_path'] + request.scope['route'].path,
                  json.dumps({"body": body_snippet}))
        raise HTTPException(status_code=401)
    elif not share_permissions.view:
        body_snippet = await _log_body_snippet(request)
        logger.warning(f"Unauthorized access - share token does not grant view access: {request.scope['route'].path}")
        log_event("unauthorized_access", None,
                  request.scope['root_path'] + request.scope['route'].path,
                  json.dumps({"body": body_snippet}))
        raise HTTPException(status_code=401)
    else:
        logger.debug(f"Auth successful using share link: {request.scope['route'].path}")
        return True


async def require_any_auth(request: Request) -> None:
    """Raise 401 immediately if the request carries no credentials at all.

    Used by URL-based lookup routes (e.g. /pk/{id}, /url/{url}) that must
    perform a DB lookup *before* they know the entity's numeric ID — and
    therefore can't run the full entity-level auth check up front.
    Without this guard, unauthenticated callers can probe whether an entity
    exists by observing the 404 vs 401 distinction in the response.
    """
    token_perms = await get_auth_permissions(request)
    if token_perms and token_perms.valid:
        return
    if request.headers.get("X-Share-Link"):
        return
    raise HTTPException(status_code=401)


async def auth_entity_view_access(request: Request, entity: T_Entities, entity_id: int):
    token_permissions = await get_auth_permissions(request)
    if not token_permissions or not token_permissions.valid:
        share_permissions = await get_share_permissions(request)
        entity_access = check_share_permissions(share_permissions, entity, entity_id)
        return await raise_share_access_error(request, entity_access)
    else:
        return await raise_auth_user_error(request, token_permissions)


async def auth_admin_access(request: Request):
    """Verify that the user has a valid admin session."""
    if os.getenv("BROWSING_PLATFORM_DEV") == "1":
        logger.debug("Admin auth bypassed - dev mode enabled")
        return True
    token_permissions = await get_auth_permissions(request)
    await raise_auth_user_error(request, token_permissions)
    if not token_permissions.admin:
        logger.warning(f"Forbidden - non-admin access attempt: {request.scope['route'].path}")
        raise HTTPException(status_code=403, detail="Admin access required")
    return token_permissions


def get_user_id(request: Request):
    if os.getenv("BROWSING_PLATFORM_DEV") == "1":
        # In dev mode there is no real session token; use the first user in the DB as a stand-in.
        row = db.execute_query("SELECT id FROM user ORDER BY id LIMIT 1", {}, "single_row")
        return row["id"] if row else None
    auth_header = request.headers.get("Authorization")
    token = parse_token_from_header(auth_header)
    token_permissions = check_token(token)
    logger.debug(f"Retrieved user_id {token_permissions.user_id}")
    return token_permissions.user_id


async def log_server_call(request: Request):
    """Log server call with user info if available"""
    logger.debug(f"Server call: {request.scope['route'].path}")
    user_id = None
    auth_header = request.headers.get("Authorization")
    token = parse_token_from_header(auth_header)
    if token:
        try:
            token_permissions = check_token(token)
            user_id = token_permissions.user_id
        except Exception:  # nosec B110 - optional enrichment for logging; failure is non-fatal
            pass
    body = await request.body()
    log_event(
        "server_call", user_id,
        request.scope['root_path'] + request.scope['route'].path,
        json.dumps({"body": body.decode("utf-8"), "path_params": request.path_params})
    )
    return True
