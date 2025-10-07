from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator
import db
import json
from extractors.entity_types import ExtractedEntitiesNested


class ArchiveSession(BaseModel):
    id: Optional[int] = None
    create_date: Optional[datetime] = None
    update_date: Optional[datetime] = None
    external_id: Optional[str] = None
    archived_url: Optional[str] = None
    archive_location: Optional[str] = None
    summary_html: Optional[str] = None
    parsed_content: Optional[int] = None
    structures: Optional[dict] = None
    metadata: Optional[dict] = None
    extracted_entities: Optional[int] = None
    archiving_timestamp: Optional[str] = None
    notes: Optional[str] = None
    extraction_error: Optional[str] = None
    source_type: int = 0

    @field_validator('metadata', 'structures', mode='before')
    def parse_data(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        return v


class ArchiveSessionWithEntities(BaseModel):
    session: ArchiveSession
    entities: ExtractedEntitiesNested


def get_archiving_session_by_id(session_id: int) -> Optional[ArchiveSession]:
    session = db.execute_query(
        """SELECT * FROM archive_session WHERE id = %(id)s""",
        {"id": session_id},
        return_type="single_row"
    )
    if session is None:
        return None
    return ArchiveSession(**session)
