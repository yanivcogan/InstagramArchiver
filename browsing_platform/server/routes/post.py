from http.client import HTTPException
from typing import Any

from fastapi import APIRouter, Depends, Request

from browsing_platform.server.routes.fast_api_request_processor import extract_entities_transform_config
from browsing_platform.server.services.enriched_entities import get_enriched_post_by_id
from browsing_platform.server.services.permissions import get_auth_user
from browsing_platform.server.services.post import get_post_by_id
from extractors.entity_types import ExtractedEntitiesNested

router = APIRouter(
    prefix="/post",
    tags=["post"],
    dependencies=[Depends(get_auth_user)],
    responses={404: {"description": "Not found"}},
)


@router.get("/data/{item_id:int}", dependencies=[Depends(get_auth_user)])
async def get_post_data(item_id:int) -> Any:
    post = get_post_by_id(item_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post Not Found")
    return post.data


@router.get("/{item_id:int}", dependencies=[Depends(get_auth_user)])
async def get_post(item_id:int, req: Request) -> ExtractedEntitiesNested:
    post = get_enriched_post_by_id(item_id, extract_entities_transform_config(req))
    if not post:
        raise HTTPException(status_code=404, detail="Post Not Found")
    return post
