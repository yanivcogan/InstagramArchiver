from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from browsing_platform.server.services.permissions import auth_user_access
from browsing_platform.server.services.tag_management import (
    ITagType, ITagDetail, ITagHierarchyEntry, ITagUsage, IQuickAccessData,
    list_tag_types, create_tag_type, update_tag_type, delete_tag_type,
    list_tags, get_tag as get_tag_service, list_quick_access_data, create_tag, update_tag, delete_tag,
    get_tag_usage_counts,
    list_children, list_parents, add_hierarchy, remove_hierarchy, would_create_cycle, update_hierarchy_notes,
    get_tag_counts_by_type,
)

router = APIRouter(
    prefix="/tag-management",
    tags=["tag-management"],
    dependencies=[Depends(auth_user_access)],
    responses={404: {"description": "Not found"}},
)


# ── Tag Type request bodies ────────────────────────────────────────────────────

class TagTypeBody(BaseModel):
    name: str
    description: Optional[str] = None
    notes: Optional[str] = None
    entity_affinity: Optional[list] = None
    quick_access: bool = False


# ── Tag request bodies ─────────────────────────────────────────────────────────

class TagBody(BaseModel):
    name: str
    description: Optional[str] = None
    tag_type_id: Optional[int] = None
    quick_access: bool = False
    omit_from_tag_type_dropdown: bool = False
    notes_recommended: bool = True

    @field_validator('name')
    @classmethod
    def name_no_commas(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Tag name cannot be empty')
        if ',' in v:
            raise ValueError('Tag name cannot contain commas')
        return v


# ── Hierarchy request bodies ───────────────────────────────────────────────────

class HierarchyBody(BaseModel):
    super_tag_id: int
    sub_tag_id: int
    notes: Optional[str] = None


class HierarchyDeleteBody(BaseModel):
    super_tag_id: int
    sub_tag_id: int


# ── Tag Type endpoints ─────────────────────────────────────────────────────────

@router.get("/types/counts/")
@router.get("/types/counts")
async def get_tag_type_counts() -> dict[str, int]:
    """Returns {type_id_str: count} plus key 'null' for untyped tags."""
    return get_tag_counts_by_type()


@router.get("/types/")
@router.get("/types")
async def get_tag_types() -> list[ITagType]:
    return list_tag_types()


@router.post("/types/")
@router.post("/types")
async def post_tag_type(body: TagTypeBody) -> ITagType:
    return create_tag_type(body.name, body.description, body.notes, body.entity_affinity, body.quick_access)


@router.put("/types/{type_id}/")
@router.put("/types/{type_id}")
async def put_tag_type(type_id: int, body: TagTypeBody) -> ITagType:
    update_tag_type(type_id, body.name, body.description, body.notes, body.entity_affinity, body.quick_access)
    return ITagType(id=type_id, **body.model_dump())


@router.delete("/types/{type_id}/")
@router.delete("/types/{type_id}")
async def del_tag_type(type_id: int) -> dict:
    ok, msg = delete_tag_type(type_id)
    if not ok:
        raise HTTPException(status_code=409, detail=msg)
    return {"ok": True}


# ── Tag endpoints ──────────────────────────────────────────────────────────────

@router.get("/quick-access/")
@router.get("/quick-access")
async def get_quick_access_tags(entity: Optional[str] = None) -> IQuickAccessData:
    return list_quick_access_data(entity)


@router.get("/tags/")
@router.get("/tags")
async def get_tags(
    tag_type_id: Optional[int] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> list[ITagDetail]:
    return list_tags(tag_type_id, q, page, page_size)


@router.get("/tags/{tag_id}/")
@router.get("/tags/{tag_id}")
async def get_tag(tag_id: int) -> ITagDetail:
    tag = get_tag_service(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


@router.post("/tags/")
@router.post("/tags")
async def post_tag(body: TagBody) -> ITagDetail:
    return create_tag(body.name, body.description, body.tag_type_id, body.quick_access, body.omit_from_tag_type_dropdown, body.notes_recommended)


@router.put("/tags/{tag_id}/")
@router.put("/tags/{tag_id}")
async def put_tag(tag_id: int, body: TagBody) -> ITagDetail:
    update_tag(tag_id, body.name, body.description, body.tag_type_id, body.quick_access, body.omit_from_tag_type_dropdown, body.notes_recommended)
    return ITagDetail(id=tag_id, **body.model_dump())


@router.delete("/tags/{tag_id}/")
@router.delete("/tags/{tag_id}")
async def del_tag(tag_id: int) -> dict:
    ok, msg = delete_tag(tag_id)
    if not ok:
        raise HTTPException(status_code=409, detail=msg)
    return {"ok": True}


@router.get("/tags/{tag_id}/usage/")
@router.get("/tags/{tag_id}/usage")
async def get_tag_usage(tag_id: int) -> ITagUsage:
    return get_tag_usage_counts(tag_id)


@router.get("/tags/{tag_id}/children/")
@router.get("/tags/{tag_id}/children")
async def get_tag_children(tag_id: int) -> list[ITagHierarchyEntry]:
    return list_children(tag_id)


@router.get("/tags/{tag_id}/parents/")
@router.get("/tags/{tag_id}/parents")
async def get_tag_parents(tag_id: int) -> list[ITagHierarchyEntry]:
    return list_parents(tag_id)


# ── Hierarchy endpoints ────────────────────────────────────────────────────────

@router.post("/hierarchy/")
@router.post("/hierarchy")
async def post_hierarchy(body: HierarchyBody) -> ITagHierarchyEntry:
    if would_create_cycle(body.super_tag_id, body.sub_tag_id):
        raise HTTPException(status_code=409, detail="Would create a cycle in tag hierarchy")
    return add_hierarchy(body.super_tag_id, body.sub_tag_id, body.notes)


@router.delete("/hierarchy/")
@router.delete("/hierarchy")
async def del_hierarchy(body: HierarchyDeleteBody) -> dict:
    remove_hierarchy(body.super_tag_id, body.sub_tag_id)
    return {"ok": True}


@router.patch("/hierarchy/")
@router.patch("/hierarchy")
async def patch_hierarchy_notes(body: HierarchyBody) -> dict:
    update_hierarchy_notes(body.super_tag_id, body.sub_tag_id, body.notes)
    return {"ok": True}
