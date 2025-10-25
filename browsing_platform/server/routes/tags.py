from typing import Any

from fastapi import APIRouter, Depends, Request

from browsing_platform.server.services.permissions import get_auth_user
from browsing_platform.server.services.tag import auto_complete_tags

router = APIRouter(
    prefix="/tags",
    tags=["tags"],
    dependencies=[Depends(get_auth_user)],
    responses={404: {"description": "Not found"}},
)


@router.get("/", dependencies=[Depends(get_auth_user)])
async def lookup_tags(req: Request) -> Any:
    search_query = req.query_params.get("q", "")
    return auto_complete_tags(search_query)

