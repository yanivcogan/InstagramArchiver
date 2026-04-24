from typing import Any, List, Literal, TypeAlias

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from browsing_platform.server.routes.fast_api_request_processor import extract_entities_transform_config
from browsing_platform.server.services.account import get_account_by_id, annotate_account
from browsing_platform.server.services.annotation import Annotation, TagWithNotes, add_tags_batch, \
    validate_tags_entity_affinity
from browsing_platform.server.services.enriched_entities import get_enriched_account_by_id, get_enriched_post_by_id, \
    get_enriched_media_by_id
from browsing_platform.server.services.media import get_media_by_id, annotate_media
from browsing_platform.server.services.media_part import get_media_part_by_id, annotate_media_part
from browsing_platform.server.services.permissions import auth_user_access
from browsing_platform.server.services.post import get_post_by_id, annotate_post
from extractors.entity_types import ExtractedEntitiesNested

router = APIRouter(
    prefix="/annotate",
    tags=["annotate"],
    dependencies=[Depends(auth_user_access)],
    responses={404: {"description": "Not found"}},
)

EntityType: TypeAlias = Literal["account", "post", "media", "media_part"]


class BatchAnnotationBody(BaseModel):
    entity_type: Literal["account", "post", "media"]
    entity_ids: List[int]
    tags: List[TagWithNotes]


@router.post("/batch", dependencies=[Depends(auth_user_access)])
async def annotate_batch(body: BatchAnnotationBody) -> bool:
    if body.tags:
        incompatible = validate_tags_entity_affinity([t.id for t in body.tags], body.entity_type)
        if incompatible:
            raise HTTPException(status_code=422, detail=f"Tags {incompatible} are not compatible with entity type '{body.entity_type}'")
    add_tags_batch(body.entity_type, body.entity_ids, body.tags)
    return True


@router.post("/{entity:str}/{item_id:int}", dependencies=[Depends(auth_user_access)])
async def annotate_entity(entity: EntityType, item_id:int, annotation: Annotation) -> Any:
    if annotation.tags:
        incompatible = validate_tags_entity_affinity([t.id for t in annotation.tags], entity)
        if incompatible:
            raise HTTPException(status_code=422, detail=f"Tags {incompatible} are not compatible with entity type '{entity}'")
    if entity == "account":
        account = get_account_by_id(item_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account Not Found")
        annotate_account(item_id, annotation)
    elif entity == "post":
        post = get_post_by_id(item_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post Not Found")
        annotate_post(item_id, annotation)
    elif entity == "media":
        media = get_media_by_id(item_id)
        if not media:
            raise HTTPException(status_code=404, detail="Media Not Found")
        annotate_media(item_id, annotation)
    elif entity == "media_part":
        media_part = get_media_part_by_id(item_id)
        if not media_part:
            raise HTTPException(status_code=404, detail="Media Part Not Found")
        annotate_media_part(item_id, annotation)
    else:
        raise HTTPException(status_code=400, detail="Invalid Entity Type")
    return True


@router.get("/{entity:str}/{item_id:int}", dependencies=[Depends(auth_user_access)])
async def get_annotatable_entity(entity: EntityType, item_id: int, req: Request) -> ExtractedEntitiesNested:
    transform = extract_entities_transform_config(req)
    if entity == "account":
        result = get_enriched_account_by_id(item_id, transform)
        label = "Account"
    elif entity == "post":
        result = get_enriched_post_by_id(item_id, transform)
        label = "Post"
    elif entity == "media" or entity == "media_part":
        result = get_enriched_media_by_id(item_id, transform)
        label = "Media"
    else:
        raise HTTPException(status_code=400, detail="Invalid Entity Type")
    if not result:
        raise HTTPException(status_code=404, detail=f"{label} Not Found")
    return result
