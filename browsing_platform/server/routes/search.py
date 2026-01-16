from fastapi import APIRouter, Depends, Request

from browsing_platform.server.routes.fast_api_request_processor import extract_search_results_config
from browsing_platform.server.services.permissions import get_auth_user
from browsing_platform.server.services.search import ISearchQuery, SearchResult, search_base

router = APIRouter(
    prefix="/search",
    tags=["search"],
    dependencies=[Depends(get_auth_user)],
    responses={404: {"description": "Not found"}},
)


@router.post("/", dependencies=[Depends(get_auth_user)])
async def search_data(query: ISearchQuery, req: Request) -> list[SearchResult]:
    return search_base(query, extract_search_results_config(req))

