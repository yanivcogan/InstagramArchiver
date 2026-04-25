from fastapi import APIRouter, Depends, HTTPException, Request

from browsing_platform.server.routes.fast_api_request_processor import extract_search_results_config
from browsing_platform.server.services.community import (
    CommunityCandidatesRequest,
    CommunityCandidatesResponse,
    compute_candidates,
)
from browsing_platform.server.services.permissions import auth_user_access

router = APIRouter(
    prefix="/community",
    tags=["community"],
    dependencies=[Depends(auth_user_access)],
    responses={404: {"description": "Not found"}},
)


@router.post("/candidates/")
async def get_community_candidates(
        req: CommunityCandidatesRequest,
        request: Request,
) -> CommunityCandidatesResponse:
    if not req.kernel_ids:
        raise HTTPException(status_code=422, detail="kernel_ids must not be empty")
    if len(req.kernel_ids) > 100:
        raise HTTPException(status_code=422, detail="kernel_ids must not exceed 100")
    transform = extract_search_results_config(request)
    return compute_candidates(req, transform)
