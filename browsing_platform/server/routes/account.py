from http.client import HTTPException

from fastapi import APIRouter, Depends

from browsing_platform.server.services.account import get_account_by_id
from browsing_platform.server.services.entities_hierarchy import nest_entities
from browsing_platform.server.services.media import get_media_by_posts
from browsing_platform.server.services.permissions import get_auth_user
from browsing_platform.server.services.post import get_posts_by_account
from extractors.entity_types import ExtractedEntitiesNested, ExtractedEntitiesFlattened

router = APIRouter(
    prefix="/analyze",
    tags=["analyze"],
    dependencies=[Depends(get_auth_user)],
    responses={404: {"description": "Not found"}},
)


@router.get("/account/{item_id:int}", , dependencies=[Depends(get_auth_user)])
async def get_account(item_id:int) -> ExtractedEntitiesNested:
    # Extract account, posts, and media using db.py helpers
    account = get_account_by_id(item_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account Not Found")
    posts = get_posts_by_account(account)
    media = get_media_by_posts(posts)

    # Flatten and nest entities
    flattened_entities = ExtractedEntitiesFlattened(
        accounts=[account],
        posts=posts,
        media=media
    )
    nested_entities = nest_entities(flattened_entities)
    return nested_entities

