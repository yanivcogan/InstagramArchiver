from typing import Optional, Literal

from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel

from browsing_platform.server.services.account import get_account_by_id, get_account_by_url
from browsing_platform.server.services.annotation import add_tags_batch, TagWithNotes
from browsing_platform.server.services.import_utils import parse_import_file
from browsing_platform.server.services.media import get_media_by_id
from browsing_platform.server.services.media_part import get_media_part_by_id
from browsing_platform.server.services.permissions import auth_user_access
from browsing_platform.server.services.post import get_post_by_id
from utils import db

router = APIRouter(
    prefix="/annotate",
    tags=["annotate"],
    dependencies=[Depends(auth_user_access)],
)

_IMPORT_COLUMNS = ["entity_type", "entity", "tag", "tag_type", "notes"]
_VALID_ENTITY_TYPES = {"account", "post", "media", "media_part"}


# ── Pydantic models ───────────────────────────────────────────────────────────

class IAnnotationImportRowInput(BaseModel):
    entity_type: str
    entity: str          # integer ID as string, or url_suffix for accounts
    tag: str             # tag name
    tag_type: Optional[str] = None
    notes: Optional[str] = None


class IResolvedAnnotationRow(BaseModel):
    row_index: int
    entity_type: str
    entity_raw: str
    entity_id: Optional[int] = None
    entity_display: Optional[str] = None
    tag_name: str
    tag_type: Optional[str] = None
    tag_id: Optional[int] = None
    notes: Optional[str] = None
    parse_errors: list[str] = []


class IAnnotationImportExecuteRequest(BaseModel):
    rows: list[IAnnotationImportRowInput]


class IAnnotationImportRowResult(BaseModel):
    row_index: int
    status: Literal['added', 'exists', 'error']
    errors: list[str] = []


class IAnnotationImportSummary(BaseModel):
    added: int = 0
    exists: int = 0
    errors: int = 0


class IAnnotationImportExecuteResponse(BaseModel):
    results: list[IAnnotationImportRowResult]
    summary: IAnnotationImportSummary


# ── Resolution helpers ────────────────────────────────────────────────────────

def _resolve_entity(entity_type: str, entity_raw: str) -> tuple[Optional[int], Optional[str], Optional[str]]:
    """Returns (entity_id, display_name, error_message)."""
    entity_type = entity_type.strip().lower()

    if entity_type not in _VALID_ENTITY_TYPES:
        return None, None, f"Invalid entity_type '{entity_type}'"

    # For non-account types, entity must be a numeric ID
    if entity_type != "account":
        if not entity_raw.strip().lstrip('-').isdigit():
            return None, None, f"Integer ID required for entity_type='{entity_type}'"
        eid = int(entity_raw.strip())
        if entity_type == "post":
            obj = get_post_by_id(eid, include_data=False)
        elif entity_type == "media":
            obj = get_media_by_id(eid, include_data=False)
        elif entity_type == "media_part":
            obj = get_media_part_by_id(eid)
        else:
            obj = None
        if obj is None:
            return None, None, f"{entity_type} with id={eid} not found"
        return eid, str(eid), None

    # Account: try numeric first, then url_suffix
    stripped = entity_raw.strip().lstrip('@')
    if stripped.isdigit():
        eid = int(stripped)
        obj = get_account_by_id(eid, include_data=False)
        if obj is None:
            return None, None, f"Account with id={eid} not found"
        display = obj.url_suffix or obj.display_name or str(eid)
        return eid, display, None
    else:
        obj = get_account_by_url(stripped, include_data=False)
        if obj is None:
            return None, None, f"Account with url_suffix='{stripped}' not found"
        return obj.id, obj.url_suffix or stripped, None


def _resolve_tag(tag_name: str, tag_type_name: Optional[str]) -> tuple[Optional[int], Optional[str]]:
    """Returns (tag_id, error_message)."""
    tag_name = tag_name.strip()
    if not tag_name:
        return None, "Tag name is required"

    if tag_type_name:
        rows = db.execute_query(
            "SELECT t.id FROM tag t JOIN tag_type tt ON t.tag_type_id = tt.id "
            "WHERE LOWER(TRIM(t.name)) = LOWER(TRIM(%(name)s)) AND LOWER(TRIM(tt.name)) = LOWER(TRIM(%(type_name)s)) LIMIT 2",
            {"name": tag_name, "type_name": tag_type_name.strip()},
            return_type="rows"
        )
    else:
        rows = db.execute_query(
            "SELECT t.id FROM tag t WHERE LOWER(TRIM(t.name)) = LOWER(TRIM(%(name)s)) LIMIT 2",
            {"name": tag_name},
            return_type="rows"
        )

    if not rows:
        suffix = f" in type '{tag_type_name}'" if tag_type_name else ""
        return None, f"Tag '{tag_name}'{suffix} not found"
    if len(rows) > 1:
        # Ambiguous — find the type names for a helpful error
        type_rows = db.execute_query(
            "SELECT COALESCE(tt.name, '(untyped)') AS tname FROM tag t "
            "LEFT JOIN tag_type tt ON t.tag_type_id = tt.id WHERE t.name = %(name)s",
            {"name": tag_name},
            return_type="rows"
        )
        type_names = ", ".join(r["tname"] for r in type_rows)
        return None, f"Tag '{tag_name}' is ambiguous — found in types: {type_names}. Specify tag_type."
    return rows[0]["id"], None


def _resolve_row(row_index: int, row: IAnnotationImportRowInput) -> IResolvedAnnotationRow:
    errors: list[str] = []

    entity_id, entity_display, entity_err = _resolve_entity(row.entity_type, row.entity)
    if entity_err:
        errors.append(entity_err)

    tag_id, tag_err = _resolve_tag(row.tag, row.tag_type)
    if tag_err:
        errors.append(tag_err)

    return IResolvedAnnotationRow(
        row_index=row_index,
        entity_type=row.entity_type.strip().lower(),
        entity_raw=row.entity,
        entity_id=entity_id,
        entity_display=entity_display,
        tag_name=row.tag,
        tag_type=row.tag_type,
        tag_id=tag_id,
        notes=row.notes or None,
        parse_errors=errors,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/import/preview/")
@router.post("/import/preview")
async def preview_annotation_import(file: UploadFile = File(...)) -> list[IResolvedAnnotationRow]:
    """Parse a CSV or XLSX file, resolve entities and tags, return resolved rows. No DB changes."""
    file_bytes = await file.read()
    raw_rows = parse_import_file(file_bytes, file.filename or "", _IMPORT_COLUMNS,
                                 required_columns=["entity_type", "entity", "tag"])

    return [
        _resolve_row(i, IAnnotationImportRowInput(
            entity_type=row.get("entity_type", ""),
            entity=row.get("entity", ""),
            tag=row.get("tag", ""),
            tag_type=row.get("tag_type") or None,
            notes=row.get("notes") or None,
        ))
        for i, row in enumerate(raw_rows)
    ]


@router.post("/import/")
@router.post("/import")
async def execute_annotation_import(
    body: IAnnotationImportExecuteRequest,
) -> IAnnotationImportExecuteResponse:
    """
    Execute annotation import. Re-resolves each row server-side for security.
    Uses INSERT IGNORE semantics (adds tags without replacing existing ones).
    """
    results: list[IAnnotationImportRowResult] = []
    summary = IAnnotationImportSummary()

    for i, row in enumerate(body.rows):
        resolved = _resolve_row(i, row)

        if resolved.parse_errors:
            results.append(IAnnotationImportRowResult(
                row_index=i, status='error', errors=resolved.parse_errors
            ))
            summary.errors += 1
            continue

        entity_id = resolved.entity_id
        tag_id = resolved.tag_id
        entity_type = resolved.entity_type

        # Check if this assignment already exists
        from browsing_platform.server.services.tag import ENTITY_TAG_TABLES
        if entity_type not in ENTITY_TAG_TABLES:
            results.append(IAnnotationImportRowResult(
                row_index=i, status='error', errors=[f"Unsupported entity_type '{entity_type}'"]
            ))
            summary.errors += 1
            continue

        table_name, id_col = ENTITY_TAG_TABLES[entity_type]
        existing = db.execute_query(
            f"SELECT 1 FROM {table_name} WHERE {id_col} = %(eid)s AND tag_id = %(tid)s",
            {"eid": entity_id, "tid": tag_id},
            return_type="single_row"
        )

        if existing:
            results.append(IAnnotationImportRowResult(row_index=i, status='exists'))
            summary.exists += 1
        else:
            db.execute_query(
                f"INSERT INTO {table_name} ({id_col}, tag_id, notes) VALUES (%(eid)s, %(tid)s, %(notes)s)",
                {"eid": entity_id, "tid": tag_id, "notes": resolved.notes},
                return_type="none"
            )
            results.append(IAnnotationImportRowResult(row_index=i, status='added'))
            summary.added += 1

    return IAnnotationImportExecuteResponse(results=results, summary=summary)
