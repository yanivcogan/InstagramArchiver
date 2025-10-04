from http.client import HTTPException

from fastapi import APIRouter, Depends

from browsing_platform.server.services.permissions import get_auth_user
from browsing_platform.server.services.enriched_entities import get_enriched_post_by_id
from extractors.entity_types import ExtractedEntitiesNested

router = APIRouter(
    prefix="/post",
    tags=["post"],
    dependencies=[Depends(get_auth_user)],
    responses={404: {"description": "Not found"}},
)


@router.get("/{item_id:int}", dependencies=[Depends(get_auth_user)])
async def get_post(item_id:int) -> ExtractedEntitiesNested:
    account = get_enriched_post_by_id(item_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account Not Found")
    return account

