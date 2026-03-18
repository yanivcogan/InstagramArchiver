import base64
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel

from browsing_platform.server.services import upload_service
from browsing_platform.server.services.permissions import auth_admin_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

MAX_UPLOAD_LENGTH = 10 * 1024 * 1024 * 1024  # 10 GB per file
TUS_VERSION = "1.0.0"
TUS_EXTENSIONS = "creation,termination"


def _tus_headers(extra: Optional[dict] = None) -> dict:
    h = {"Tus-Resumable": TUS_VERSION}
    if extra:
        h.update(extra)
    return h


def _decode_tus_metadata(raw: str) -> dict:
    """Decode TUS Upload-Metadata header (comma-separated 'key base64value' pairs)."""
    result = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        parts = pair.split(" ", 1)
        key = parts[0]
        value = base64.b64decode(parts[1]).decode("utf-8") if len(parts) > 1 else ""
        result[key] = value
    return result


# ---------------------------------------------------------------------------
# Preflight — check which archive names already exist
# ---------------------------------------------------------------------------

class PreflightRequest(BaseModel):
    archives: list[str]


@router.post("/preflight")
def preflight(body: PreflightRequest, _=Depends(auth_admin_access)):
    for name in body.archives:
        if not upload_service.validate_archive_name(name):
            raise HTTPException(status_code=400, detail=f"Invalid archive name: {name!r}")
    return {"conflicts": upload_service.check_conflicts(body.archives)}


# ---------------------------------------------------------------------------
# TUS protocol endpoints
# ---------------------------------------------------------------------------

@router.options("/tus")
def tus_options(_=Depends(auth_admin_access)):
    return Response(
        status_code=204,
        headers={
            **_tus_headers(),
            "Tus-Version": TUS_VERSION,
            "Tus-Extension": TUS_EXTENSIONS,
            "Tus-Max-Size": str(MAX_UPLOAD_LENGTH),
        },
    )


@router.post("/tus/")
def tus_create(
    request: Request,
    upload_length: Optional[int] = Header(None, alias="Upload-Length"),
    upload_metadata: Optional[str] = Header(None, alias="Upload-Metadata"),
    _=Depends(auth_admin_access),
):
    if upload_length is None:
        raise HTTPException(status_code=400, detail="Upload-Length header required")
    if upload_length > MAX_UPLOAD_LENGTH:
        raise HTTPException(status_code=413, detail="File too large")

    metadata = _decode_tus_metadata(upload_metadata or "")
    archive_name = metadata.get("archiveName", "")
    relative_path = metadata.get("relativePath", "")
    file_hash = metadata.get("fileHash") or None  # hex SHA-256 declared by client

    if not upload_service.validate_archive_name(archive_name):
        raise HTTPException(status_code=400, detail="Invalid archive name")
    if not upload_service.validate_file_path(relative_path):
        raise HTTPException(status_code=400, detail="Invalid file path")

    file_id = upload_service.create_upload(archive_name, relative_path, upload_length, file_hash)
    # Build absolute URL for Location header
    base = str(request.base_url).rstrip("/")
    location = f"{base}/api/upload/tus/{file_id}"

    return Response(
        status_code=201,
        headers=_tus_headers({"Location": location, "Upload-Offset": "0"}),
    )


@router.head("/tus/{file_id}")
def tus_head(file_id: str, _=Depends(auth_admin_access)):
    state = upload_service.get_upload_state(file_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return Response(
        status_code=200,
        headers=_tus_headers({
            "Upload-Offset": str(state["offset"]),
            "Upload-Length": str(state["upload_length"]),
            "Cache-Control": "no-store",
        }),
    )


@router.patch("/tus/{file_id}")
async def tus_patch(
    file_id: str,
    request: Request,
    content_type: Optional[str] = Header(None, alias="Content-Type"),
    upload_offset: Optional[int] = Header(None, alias="Upload-Offset"),
    _=Depends(auth_admin_access),
):
    if content_type != "application/offset+octet-stream":
        raise HTTPException(status_code=415, detail="Content-Type must be application/offset+octet-stream")
    if upload_offset is None:
        raise HTTPException(status_code=400, detail="Upload-Offset header required")

    data = await request.body()

    try:
        new_offset = upload_service.patch_upload(file_id, upload_offset, data)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Upload not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return Response(
        status_code=204,
        headers=_tus_headers({"Upload-Offset": str(new_offset)}),
    )


@router.delete("/tus/{file_id}")
def tus_delete(file_id: str, _=Depends(auth_admin_access)):
    upload_service.delete_upload(file_id)
    return Response(status_code=204, headers=_tus_headers())


# ---------------------------------------------------------------------------
# Verify & commit
# ---------------------------------------------------------------------------

@router.post("/verify/{archive_name}")
def verify(archive_name: str, _=Depends(auth_admin_access)):
    if not upload_service.validate_archive_name(archive_name):
        raise HTTPException(status_code=400, detail="Invalid archive name")
    return upload_service.verify_archive(archive_name)


@router.post("/commit/{archive_name}")
def commit(archive_name: str, request: Request, permissions=Depends(auth_admin_access)):
    if not upload_service.validate_archive_name(archive_name):
        raise HTTPException(status_code=400, detail="Invalid archive name")

    # Best-effort uploader identity — captured for chain-of-custody record
    client_ip = (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else None)
    )
    user_id = getattr(permissions, "user_id", None)  # None in dev-bypass mode

    uploader_info = {
        "user_id": user_id,
        "ip_address": client_ip,
        "user_agent": request.headers.get("User-Agent"),
        "x_forwarded_for": request.headers.get("X-Forwarded-For"),
    }

    try:
        upload_service.commit_archive(archive_name, uploader_info)
    except Exception as e:
        logger.error(f"Failed to commit archive '{archive_name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to commit archive")
    return {"status": "ok"}


@router.delete("/staging/{archive_name}")
def delete_staging(archive_name: str, _=Depends(auth_admin_access)):
    if not upload_service.validate_archive_name(archive_name):
        raise HTTPException(status_code=400, detail="Invalid archive name")
    upload_service.cleanup_staging_archive(archive_name)
    return {"status": "ok"}
