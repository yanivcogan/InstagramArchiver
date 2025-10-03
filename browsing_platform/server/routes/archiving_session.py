from http.client import HTTPException

from fastapi import APIRouter, Depends

from browsing_platform.server.services.account import get_enriched_account_by_id
from browsing_platform.server.services.permissions import get_auth_user
from extractors.entity_types import ExtractedEntitiesNested

router = APIRouter(
    prefix="/archiving_session",
    tags=["archiving_session"],
    dependencies=[Depends(get_auth_user)],
    responses={404: {"description": "Not found"}},
)


@router.get("/{item_id:int}", dependencies=[Depends(get_auth_user)])
async def get_archiving_session(item_id:int) -> ExtractedEntitiesNested:
    account = get_enriched_account_by_id(item_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account Not Found")
    return account

