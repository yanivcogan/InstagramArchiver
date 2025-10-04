from typing import Optional
from pydantic import BaseModel
import db
from extractors.entity_types import ExtractedEntitiesNested


class ArchiveSession(BaseModel):
    id: Optional[int]
    create_date: Optional[str]
    update_date: Optional[str]
    external_id: Optional[str]
    archived_url: Optional[str]
    archive_location: Optional[str]
    summary_html: Optional[str]
    parsed_content: Optional[int]
    structures: Optional[dict]
    metadata: Optional[dict]
    extracted_entities: Optional[int]
    archiving_timestamp: Optional[str]
    notes: Optional[str]
    extraction_error: Optional[str]
    source_type: int = 0


class ArchiveSessionWithEntities(BaseModel):
    session: ArchiveSession
    entities: ExtractedEntitiesNested


def get_archiving_session_by_id(session_id: int) -> Optional[ArchiveSession]:
    session = db.execute_query(
        """SELECT * FROM archive_session WHERE id LIKE %(id)s""",
        {"id": session_id},
        return_type="single_row"
    )
    if session is None:
        return None
    return ArchiveSession(**session)
