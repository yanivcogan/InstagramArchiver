from fastapi import APIRouter, Request

from browsing_platform.server.services.permissions import parse_token_from_header
from browsing_platform.server.services.token_manager import check_token, TokenPermissions

router = APIRouter(
    prefix="/permissions",
    tags=["permissions"],
    responses={404: {"description": "Not found"}},
)


@router.get("/")
async def get_permissions(request: Request):
    token = parse_token_from_header(request.headers.get("Authorization"))
    if not token:
        return TokenPermissions(valid=False, admin=False, user_id=None)
    token_permissions = check_token(token)
    return token_permissions