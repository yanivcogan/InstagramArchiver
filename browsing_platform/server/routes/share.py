from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from browsing_platform.server.services.entities_hierarchy import T_Entities
from browsing_platform.server.services.permissions import auth_user_access, get_user_id
from browsing_platform.server.services.sharing_manager import (
    EntitySharePermissions,
    create_share_link,
    get_existing_share_link,
    set_link_validity,
)

router = APIRouter(
    prefix="/share",
    tags=["share"],
    dependencies=[Depends(auth_user_access)],
    responses={404: {"description": "Not found"}},
)


@router.post("/", dependencies=[Depends(auth_user_access)])
async def new_share_link(scope: EntitySharePermissions, req: Request) -> Any:
    user_id = get_user_id(req)
    return create_share_link(scope, user_id)


@router.get("/{entity}/{entity_id}/", dependencies=[Depends(auth_user_access)])
async def get_share_link(entity: T_Entities, entity_id: int) -> Any:
    existing = get_existing_share_link(entity, entity_id)
    if not existing:
        return None
    return {"link_suffix": existing.link_suffix, "valid": existing.valid}


class SetValidityRequest(BaseModel):
    valid: bool


@router.post("/{entity}/{entity_id}/valid", dependencies=[Depends(auth_user_access)])
async def patch_share_link_validity(entity: T_Entities, entity_id: int, body: SetValidityRequest) -> Any:
    existing = get_existing_share_link(entity, entity_id)
    if not existing:
        raise HTTPException(status_code=404, detail="No share link found for this entity")
    set_link_validity(existing.link_suffix, body.valid)
    return {"success": True}

