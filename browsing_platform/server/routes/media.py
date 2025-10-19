from http.client import HTTPException
from typing import Any

from fastapi import APIRouter, Depends, Request

from browsing_platform.server.routes.fast_api_request_processor import extract_entities_transform_config
from browsing_platform.server.services.enriched_entities import get_enriched_media_by_id
from browsing_platform.server.services.media import get_media_by_id
from browsing_platform.server.services.permissions import get_auth_user
from extractors.entity_types import ExtractedEntitiesNested

router = APIRouter(
    prefix="/media",
    tags=["media"],
    dependencies=[Depends(get_auth_user)],
    responses={404: {"description": "Not found"}},
)


@router.get("/data/{item_id:int}", dependencies=[Depends(get_auth_user)])
async def get_media_data(item_id:int) -> Any:
    media = get_media_by_id(item_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media Not Found")
    return media.data


@router.get("/{item_id:int}", dependencies=[Depends(get_auth_user)])
async def get_media(item_id:int, req: Request) -> ExtractedEntitiesNested:
    media = get_enriched_media_by_id(item_id, extract_entities_transform_config(req))
    if not media:
        raise HTTPException(status_code=404, detail="Media Not Found")
    return media
