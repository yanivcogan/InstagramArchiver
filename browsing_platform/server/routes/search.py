from fastapi import APIRouter, Depends

from browsing_platform.server.services.permissions import get_auth_user
from browsing_platform.server.services.search import ISearchQuery, SearchResult, search_base

router = APIRouter(
    prefix="/search",
    tags=["search"],
    dependencies=[Depends(get_auth_user)],
    responses={404: {"description": "Not found"}},
)


@router.post("/", dependencies=[Depends(get_auth_user)])
async def search_data(query: ISearchQuery) -> list[SearchResult]:
    return search_base(query)

