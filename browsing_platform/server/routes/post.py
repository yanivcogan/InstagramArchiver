from fastapi import HTTPException
from typing import Any

from fastapi import APIRouter, Depends, Request

from browsing_platform.server.routes.fast_api_request_processor import extract_entities_transform_config
from browsing_platform.server.services.enriched_entities import get_enriched_post_by_id, get_comments_by_post_ids, \
    get_likes_by_post_id
from browsing_platform.server.services.permissions import auth_entity_view_access
from browsing_platform.server.services.post import get_post_by_id, get_post_data_by_id, post_exists, \
    get_post_by_platform_id, get_post_by_url
from extractors.entity_types import ExtractedEntitiesNested, Comment, Like

router = APIRouter(
    prefix="/post",
    tags=["post"],
    dependencies=[],
    responses={404: {"description": "Not found"}},
)


async def _auth_post_view(req: Request, item_id: int):
    return await auth_entity_view_access(request=req, entity="post", entity_id=item_id)


@router.get("/pk/{platform_id}/")
@router.get("/pk/{platform_id}")
async def get_post_by_pk(platform_id: str, req: Request) -> ExtractedEntitiesNested:
    post = get_post_by_platform_id(platform_id, include_data=False)
    if not post:
        raise HTTPException(status_code=404, detail="Post Not Found")
    await auth_entity_view_access(request=req, entity="post", entity_id=post.id)
    return get_enriched_post_by_id(post.id, extract_entities_transform_config(req))


@router.get("/url/{post_url:path}")
async def get_post_by_url_path(post_url: str, req: Request) -> ExtractedEntitiesNested:
    post = get_post_by_url(post_url, include_data=False)
    if not post:
        raise HTTPException(status_code=404, detail="Post Not Found")
    await auth_entity_view_access(request=req, entity="post", entity_id=post.id)
    return get_enriched_post_by_id(post.id, extract_entities_transform_config(req))


@router.get("/data/{item_id}/", dependencies=[Depends(_auth_post_view)])
@router.get("/data/{item_id}", dependencies=[Depends(_auth_post_view)])
async def get_post_data(item_id:int) -> Any:
    found, data = get_post_data_by_id(item_id)
    if not found:
        raise HTTPException(status_code=404, detail="Post Not Found")
    return data


@router.get("/{item_id}/comments/", dependencies=[Depends(_auth_post_view)])
@router.get("/{item_id}/comments", dependencies=[Depends(_auth_post_view)])
async def get_post_comments(item_id: int) -> list[Comment]:
    if not post_exists(item_id):
        raise HTTPException(status_code=404, detail="Post Not Found")
    return get_comments_by_post_ids([item_id])


@router.get("/{item_id}/likes/", dependencies=[Depends(_auth_post_view)])
@router.get("/{item_id}/likes", dependencies=[Depends(_auth_post_view)])
async def get_post_likes(item_id: int) -> list[Like]:
    if not post_exists(item_id):
        raise HTTPException(status_code=404, detail="Post Not Found")
    return get_likes_by_post_id(item_id)


@router.get("/{item_id}/", dependencies=[Depends(_auth_post_view)])
@router.get("/{item_id}", dependencies=[Depends(_auth_post_view)])
async def get_post(item_id:int, req: Request) -> ExtractedEntitiesNested:
    post = get_enriched_post_by_id(item_id, extract_entities_transform_config(req))
    if not post:
        raise HTTPException(status_code=404, detail="Post Not Found")
    return post
