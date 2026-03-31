from typing import Any

from fastapi import APIRouter, Depends, Request

from browsing_platform.server.services.permissions import auth_user_access
from browsing_platform.server.services.tag import auto_complete_tags, get_tags_by_entity_ids, ENTITY_TAG_TABLES

router = APIRouter(
    prefix="/tags",
    tags=["tags"],
    dependencies=[Depends(auth_user_access)],
    responses={404: {"description": "Not found"}},
)


@router.get("/", dependencies=[Depends(auth_user_access)])
async def lookup_tags(req: Request) -> Any:
    search_query = req.query_params.get("q", "")
    tag_type_id_raw = req.query_params.get("tag_type_id", None)
    tag_type_id = int(tag_type_id_raw) if tag_type_id_raw else None
    entity = req.query_params.get("entity", None)
    return auto_complete_tags(search_query, tag_type_id, entity)


@router.get("/by-entities/", dependencies=[Depends(auth_user_access)])
async def get_tags_for_entities(req: Request) -> Any:
    entity = req.query_params.get("entity", "")
    ids_raw = req.query_params.get("ids", "")
    ids = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()]
    if not ids or entity not in ENTITY_TAG_TABLES:
        return {}
    result = get_tags_by_entity_ids(entity, ids)
    return {str(k): [v.model_dump() for v in vs] for k, vs in result.items()}

