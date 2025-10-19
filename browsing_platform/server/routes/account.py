from http.client import HTTPException
from typing import Any

from fastapi import APIRouter, Depends, Request

from browsing_platform.server.routes.fast_api_request_processor import extract_entities_transform_config
from browsing_platform.server.services.account import get_account_by_id
from browsing_platform.server.services.enriched_entities import get_enriched_account_by_id
from browsing_platform.server.services.permissions import get_auth_user
from extractors.entity_types import ExtractedEntitiesNested

router = APIRouter(
    prefix="/account",
    tags=["account"],
    dependencies=[Depends(get_auth_user)],
    responses={404: {"description": "Not found"}},
)

@router.get("/data/{item_id:int}", dependencies=[Depends(get_auth_user)])
async def get_account_data(item_id:int) -> Any:
    account = get_account_by_id(item_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account Not Found")
    return account.data


@router.get("/{item_id:int}", dependencies=[Depends(get_auth_user)])
async def get_account(item_id:int, req: Request) -> ExtractedEntitiesNested:
    account = get_enriched_account_by_id(item_id, extract_entities_transform_config(req))
    if not account:
        raise HTTPException(status_code=404, detail="Account Not Found")
    return account
