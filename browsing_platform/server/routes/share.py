from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from browsing_platform.server.services.entities_hierarchy import T_Entities
from browsing_platform.server.services.permissions import auth_user_access, get_user_id
from browsing_platform.server.services.sharing_manager import (
    EntitySharePermissions,
    create_share_link,
    entity_exists,
    get_existing_share_link,
    set_link_attachment_access,
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
    if scope.shared_entity is None:
        raise HTTPException(status_code=400, detail="shared_entity is required")
    if not entity_exists(scope.shared_entity.entity, scope.shared_entity.entity_id):
        raise HTTPException(status_code=404, detail=f"{scope.shared_entity.entity} not found")
    user_id = get_user_id(req)
    return create_share_link(scope, user_id)


@router.get("/{entity}/{entity_id}/", dependencies=[Depends(auth_user_access)])
async def get_share_link(entity: T_Entities, entity_id: int) -> Any:
    existing = get_existing_share_link(entity, entity_id)
    if not existing:
        return None
    return {
        "link_suffix": existing.link_suffix,
        "valid": existing.valid,
        "include_screen_recordings": existing.include_screen_recordings,
        "include_har": existing.include_har,
    }


class SetValidityRequest(BaseModel):
    valid: bool


@router.post("/{entity}/{entity_id}/valid", dependencies=[Depends(auth_user_access)])
async def patch_share_link_validity(entity: T_Entities, entity_id: int, body: SetValidityRequest) -> Any:
    existing = get_existing_share_link(entity, entity_id)
    if not existing:
        raise HTTPException(status_code=404, detail="No share link found for this entity")
    set_link_validity(existing.link_suffix, body.valid)
    return {"success": True}


class SetAttachmentAccessRequest(BaseModel):
    include_screen_recordings: bool
    include_har: bool


@router.post("/{entity}/{entity_id}/attachment_access", dependencies=[Depends(auth_user_access)])
async def patch_share_link_attachment_access(
    entity: T_Entities, entity_id: int, body: SetAttachmentAccessRequest
) -> Any:
    existing = get_existing_share_link(entity, entity_id)
    if not existing:
        raise HTTPException(status_code=404, detail="No share link found for this entity")
    set_link_attachment_access(existing.link_suffix, body.include_screen_recordings, body.include_har)
    return {"success": True}

