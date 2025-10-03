from typing import Optional
from pydantic import BaseModel
import db
from browsing_platform.server.services.entities_hierarchy import nest_entities
from browsing_platform.server.services.media import get_media_by_posts
from browsing_platform.server.services.post import get_posts_by_accounts
from extractors.entity_types import Account, ExtractedEntitiesNested, ExtractedEntitiesFlattened, Post, Media


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


def get_enriched_archiving_session_by_id(session_id: int) -> Optional[ArchiveSessionWithEntities]:
    session = get_archiving_session_by_id(session_id)
    if session is None:
        return None
    account_rows = db.execute_query(
        """SELECT a.id, aa.url, aa.archive_session_id, aa.display_name, aa.bio
            FROM account_archive AS aa
            LEFT JOIN account AS a ON aa.canonical_id = a.id
            WHERE archive_session_id LIKE %(id)s
        """,
        {"id": session_id},
        return_type="rows"
    )
    post_rows = db.execute_query(
        """SELECT p.id, p.account_id, pa.url, pa.archive_session_id, pa.caption, pa.publication_date, pa.data
            FROM post_archive AS pa 
            LEFT JOIN post AS p ON pa.canonical_id = p.id
            WHERE archive_session_id LIKE %(id)s
        """,
        {"id": session_id},
        return_type="rows"
    )
    media_rows = db.execute_query(
        """SELECT m.id, m.post_id, ma.url, ma.local_url, ma.archive_session_id, ma.media_type, ma.data
            FROM media_archive AS ma
            LEFT JOIN media AS m ON ma.canonical_id = m.id
            WHERE archive_session_id LIKE %(id)s
        """,
        {"id": session_id},
        return_type="rows"
    )
    accounts = [Account(**a) for a in account_rows]
    posts = [Post(**p) for p in post_rows]
    media = [Media(**m) for m in media_rows]

    # Flatten and nest entities
    flattened_entities = ExtractedEntitiesFlattened(
        accounts=accounts,
        posts=posts,
        media=media
    )
    nested_entities = nest_entities(flattened_entities)
    return ArchiveSessionWithEntities(
        session=session,
        entities=nested_entities
    )
