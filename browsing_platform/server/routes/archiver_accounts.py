"""Admin management of the archiver-account roster and its access index.

Sensitive data (operators' account identities + social graph). The whole router
is admin-only. Roster CRUD writes the `archiver_account` table; export ingestion
rebuilds `archiver_account_access` from an uploaded Instagram data-export folder.

The export files themselves are transferred via the shared TUS upload endpoints
(routes/upload.py, also admin-only) into the upload staging area; this router's
`/{id}/ingest-staged` endpoint then parses the staged folder and deletes it.
See services/archiver_access.py and db_loaders/archiver_access_loader.py.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from browsing_platform.server.services import archiver_access
from browsing_platform.server.services.permissions import auth_admin_access

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/archiver-accounts",
    tags=["admin"],
    dependencies=[Depends(auth_admin_access)],
    responses={404: {"description": "Not found"}},
)


class LabelRequest(BaseModel):
    label: str


class IngestStagedRequest(BaseModel):
    staging_name: str


class CreatedArchiverAccount(BaseModel):
    id: int
    label: str


def _clean_label(label: str) -> str:
    label = (label or "").strip()
    if not label:
        raise HTTPException(status_code=422, detail="Label is required")
    if len(label) > 200:
        raise HTTPException(status_code=422, detail="Label too long (max 200 chars)")
    return label


@router.get("/")
async def list_archiver_accounts() -> list[archiver_access.ArchiverAccountSummary]:
    return archiver_access.list_archiver_accounts_with_counts()


@router.post("/")
async def create_archiver_account(body: LabelRequest) -> CreatedArchiverAccount:
    label = _clean_label(body.label)
    if archiver_access.get_archiver_account_id_by_label(label) is not None:
        raise HTTPException(status_code=409, detail="An archiver account with this label already exists")
    new_id = archiver_access.insert_archiver_account(label)
    return CreatedArchiverAccount(id=new_id, label=label)


@router.patch("/{archiver_account_id}")
async def rename_archiver_account(archiver_account_id: int, body: LabelRequest) -> dict:
    if archiver_access.get_archiver_account_row(archiver_account_id) is None:
        raise HTTPException(status_code=404, detail="Archiver account not found")
    label = _clean_label(body.label)
    existing = archiver_access.get_archiver_account_id_by_label(label)
    if existing is not None and existing != archiver_account_id:
        raise HTTPException(status_code=409, detail="An archiver account with this label already exists")
    archiver_access.update_archiver_account_label(archiver_account_id, label)
    return {"success": True}


@router.delete("/{archiver_account_id}")
async def delete_archiver_account(archiver_account_id: int) -> dict:
    if archiver_access.get_archiver_account_row(archiver_account_id) is None:
        raise HTTPException(status_code=404, detail="Archiver account not found")
    archiver_access.delete_archiver_account(archiver_account_id)
    return {"success": True}


@router.post("/{archiver_account_id}/ingest-staged")
async def ingest_staged_export(
    archiver_account_id: int, body: IngestStagedRequest
) -> archiver_access.ArchiverAccountCounts:
    if archiver_access.get_archiver_account_row(archiver_account_id) is None:
        raise HTTPException(status_code=404, detail="Archiver account not found")
    try:
        return archiver_access.process_staged_export(archiver_account_id, body.staging_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
