from typing import Optional, Literal

from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel, field_validator

from browsing_platform.server.services.import_utils import parse_import_file
from browsing_platform.server.services.permissions import auth_user_access
from browsing_platform.server.services.tag_management import (
    get_tag_type_by_name, create_tag_type, upsert_tag,
    add_hierarchy_ignore_duplicate, get_tag_by_name_and_type,
)

router = APIRouter(
    prefix="/tag-management",
    tags=["tag-management"],
    dependencies=[Depends(auth_user_access)],
)

_IMPORT_COLUMNS = ["name", "tag_type", "description", "quick_access", "parents"]

_BOOL_TRUE = {"true", "1", "yes"}
_BOOL_FALSE = {"false", "0", "no", ""}


def _parse_bool(val: str) -> bool:
    return val.strip().lower() in _BOOL_TRUE


def _parse_parents(val: str) -> list[str]:
    if not val.strip():
        return []
    return [p.strip() for p in val.split("|") if p.strip()]


# ── Pydantic models ───────────────────────────────────────────────────────────

class ITagImportParseError(BaseModel):
    field: str
    message: str


class ITagImportRowInput(BaseModel):
    name: str
    tag_type: Optional[str] = None
    description: Optional[str] = None
    quick_access: bool = False
    parents: list[str] = []

    @field_validator('name')
    @classmethod
    def name_no_commas(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Tag name cannot be empty')
        if ',' in v:
            raise ValueError('Tag name cannot contain commas')
        return v


class ITagImportRowParsed(BaseModel):
    row_index: int
    name: str
    tag_type: Optional[str] = None
    description: Optional[str] = None
    quick_access: bool = False
    parents: list[str] = []
    parse_errors: list[ITagImportParseError] = []


class ITagImportExecuteRequest(BaseModel):
    rows: list[ITagImportRowInput]
    create_missing_types: bool = False


class ITagRelationshipResult(BaseModel):
    parent_name: str
    status: Literal['added', 'exists', 'cycle', 'parent_not_found']


class ITagImportRowResult(BaseModel):
    row_index: int
    status: Literal['created', 'existing', 'error'] = 'error'
    tag_id: Optional[int] = None
    tag_name: str
    errors: list[str] = []
    relationships: list[ITagRelationshipResult] = []


class ITagImportSummary(BaseModel):
    created: int = 0
    existing: int = 0
    errors: int = 0
    relationships_added: int = 0
    cycles_skipped: int = 0


class ITagImportExecuteResponse(BaseModel):
    results: list[ITagImportRowResult]
    summary: ITagImportSummary


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/import/tags/preview/")
@router.post("/import/tags/preview")
async def preview_tag_import(file: UploadFile = File(...)) -> list[ITagImportRowParsed]:
    """Parse a CSV or XLSX file and return rows with inline validation errors. No DB changes."""
    file_bytes = await file.read()
    raw_rows = parse_import_file(file_bytes, file.filename or "", _IMPORT_COLUMNS, required_columns=["name"])

    result = []
    for i, row in enumerate(raw_rows):
        errors: list[ITagImportParseError] = []
        name = row.get("name", "").strip()

        if not name:
            errors.append(ITagImportParseError(field="name", message="Name is required"))
        elif ',' in name:
            errors.append(ITagImportParseError(field="name", message="Name cannot contain commas"))

        quick_access_raw = row.get("quick_access", "").strip().lower()
        if quick_access_raw and quick_access_raw not in _BOOL_TRUE and quick_access_raw not in _BOOL_FALSE:
            errors.append(ITagImportParseError(
                field="quick_access",
                message=f"Invalid value '{quick_access_raw}' — use true/false/1/0/yes/no"
            ))

        result.append(ITagImportRowParsed(
            row_index=i,
            name=name,
            tag_type=row.get("tag_type") or None,
            description=row.get("description") or None,
            quick_access=_parse_bool(row.get("quick_access", "")),
            parents=_parse_parents(row.get("parents", "")),
            parse_errors=errors,
        ))

    return result


@router.post("/import/tags/")
@router.post("/import/tags")
async def execute_tag_import(body: ITagImportExecuteRequest) -> ITagImportExecuteResponse:
    """
    Execute a tag import. Two-pass:
    1. Resolve/create tag types, upsert tags → build name→id map
    2. Resolve parent names, add hierarchy relationships
    """
    results: list[ITagImportRowResult] = []
    summary = ITagImportSummary()

    # Pass 1: upsert all tags, build name→id lookup
    tag_id_map: dict[str, int] = {}  # tag_name → tag_id (from this import batch)

    for i, row in enumerate(body.rows):
        row_result = ITagImportRowResult(row_index=i, tag_name=row.name)

        # Resolve tag type
        tag_type_id: Optional[int] = None
        if row.tag_type:
            tt = get_tag_type_by_name(row.tag_type)
            if tt is None:
                if body.create_missing_types:
                    tt = create_tag_type(row.tag_type, None, None, None)
                else:
                    row_result.status = 'error'
                    row_result.errors.append(f"Tag type '{row.tag_type}' not found")
                    results.append(row_result)
                    summary.errors += 1
                    continue
            tag_type_id = tt.id

        # Upsert tag
        try:
            tag, was_created = upsert_tag(row.name, row.description, tag_type_id, row.quick_access)
            row_result.tag_id = tag.id
            row_result.status = 'created' if was_created else 'existing'
            tag_id_map[row.name] = tag.id
            if was_created:
                summary.created += 1
            else:
                summary.existing += 1
        except Exception as e:
            row_result.status = 'error'
            row_result.errors.append(str(e))
            summary.errors += 1

        results.append(row_result)

    # Pass 2: add hierarchy relationships
    for i, row in enumerate(body.rows):
        row_result = results[i]
        if row_result.status == 'error' or not row.parents:
            continue

        child_id = row_result.tag_id
        if child_id is None:
            continue

        for parent_name in row.parents:
            # Look up parent from this batch first, then from DB
            parent_id = tag_id_map.get(parent_name)
            if parent_id is None:
                # Try to find in DB (any tag_type)
                db_parent = _find_tag_by_name_any_type(parent_name)
                if db_parent is None:
                    row_result.relationships.append(
                        ITagRelationshipResult(parent_name=parent_name, status='parent_not_found')
                    )
                    continue
                parent_id = db_parent

            status = add_hierarchy_ignore_duplicate(super_tag_id=parent_id, sub_tag_id=child_id)
            row_result.relationships.append(ITagRelationshipResult(parent_name=parent_name, status=status))
            if status == 'added':
                summary.relationships_added += 1
            elif status == 'cycle':
                summary.cycles_skipped += 1

    return ITagImportExecuteResponse(results=results, summary=summary)


def _find_tag_by_name_any_type(name: str) -> Optional[int]:
    """Find a tag by name (case-insensitive, trimmed) across all types. Returns tag_id or None."""
    from utils import db
    rows = db.execute_query(
        "SELECT id FROM tag WHERE LOWER(TRIM(name)) = LOWER(TRIM(%(name)s)) LIMIT 2",
        {"name": name},
        return_type="rows"
    )
    if len(rows) == 1:
        return rows[0]["id"]
    # Multiple or zero — return None; caller should handle
    return None if not rows else rows[0]["id"]
