from typing import Optional

import db
from browsing_platform.server.services.account import get_account_by_id
from browsing_platform.server.services.archiving_session import ArchiveSessionWithEntities, get_archiving_session_by_id
from browsing_platform.server.services.entities_hierarchy import nest_entities
from browsing_platform.server.services.media import get_media_by_posts
from browsing_platform.server.services.post import get_post_by_id, get_posts_by_accounts
from extractors.entity_types import ExtractedEntitiesNested, Media, ExtractedEntitiesFlattened, Account, Post


def get_enriched_media_by_id(media_id: int) -> Optional[ExtractedEntitiesNested]:
    row = db.execute_query(
        """SELECT *
           FROM media
           WHERE id LIKE %(id)s""",
        {"id": media_id},
        return_type="single_row"
    )
    if row is None:
        return None

    media = Media(**row)
    post = get_post_by_id(media.post_id)
    account = get_account_by_id(post.account_id)

    # Flatten and nest entities
    flattened_entities = ExtractedEntitiesFlattened(
        accounts=[account],
        posts=[post],
        media=[media]
    )
    nested_entities = nest_entities(flattened_entities)
    return nested_entities


def get_enriched_post_by_id(post_id: int) -> Optional[ExtractedEntitiesNested]:
    post = get_post_by_id(post_id)
    if post is None:
        return None
    account = get_account_by_id(post.account_id)
    media = get_media_by_posts([post])

    # Flatten and nest entities
    flattened_entities = ExtractedEntitiesFlattened(
        accounts=[account],
        posts=[post],
        media=media
    )
    nested_entities = nest_entities(flattened_entities)
    return nested_entities


def get_enriched_account_by_id(account_id: int) -> Optional[ExtractedEntitiesNested]:
    account = get_account_by_id(account_id)
    if account is None:
        return None
    posts = get_posts_by_accounts([account])
    media = get_media_by_posts(posts)

    # Flatten and nest entities
    flattened_entities = ExtractedEntitiesFlattened(
        accounts=[account],
        posts=posts,
        media=media
    )
    nested_entities = nest_entities(flattened_entities)
    return nested_entities


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
