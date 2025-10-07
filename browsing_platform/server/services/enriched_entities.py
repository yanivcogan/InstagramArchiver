from typing import Optional
from pydantic import BaseModel

import db
from browsing_platform.server.services.account import get_account_by_id
from browsing_platform.server.services.archiving_session import ArchiveSessionWithEntities, get_archiving_session_by_id, \
    ArchiveSession
from browsing_platform.server.services.entities_hierarchy import nest_entities
from browsing_platform.server.services.media import get_media_by_posts
from browsing_platform.server.services.post import get_post_by_id, get_posts_by_accounts
from extractors.db_intake import LOCAL_ARCHIVES_DIR_ALIAS
from extractors.entity_types import ExtractedEntitiesNested, Media, ExtractedEntitiesFlattened, Account, Post


class FlattenedEntitiesTransform(BaseModel):
    local_files_root: Optional[str] = None
    retain_only_media_with_local_files: bool = False


def apply_flattened_entities_transform(
        entities: ExtractedEntitiesFlattened,
        transform: FlattenedEntitiesTransform
) -> ExtractedEntitiesFlattened:
    if transform.retain_only_media_with_local_files:
        entities.media = [
            m for m in entities.media if m.local_url is not None and m.local_url.strip() != ""
        ]
    if transform.local_files_root is not None:
        for m in entities.media:
            if m.local_url is not None and m.local_url.strip() != "":
                if m.local_url.startswith(f"{LOCAL_ARCHIVES_DIR_ALIAS}/"):
                    m.local_url = m.local_url.replace(LOCAL_ARCHIVES_DIR_ALIAS, transform.local_files_root, 1)
    return entities


class NestedEntitiesTransform(BaseModel):
    retain_only_posts_with_media: bool = False
    retain_only_accounts_with_posts: bool = False


def apply_nested_entities_transform(
        entities: ExtractedEntitiesNested,
        transform: NestedEntitiesTransform
) -> ExtractedEntitiesNested:
    if transform.retain_only_posts_with_media:
        entities.posts = [
            p for p in entities.posts if p.post_media and len(p.post_media) > 0
        ]
        for account in entities.accounts:
            account.account_posts = [
                p for p in account.account_posts if p.post_media and len(p.post_media) > 0
            ]
    if transform.retain_only_accounts_with_posts:
        entities.accounts = [
            a for a in entities.accounts if a.account_posts and len(a.account_posts) > 0
        ]
    return entities


class EntitiesTransformConfig(BaseModel):
    flattened_entities_transform: Optional[FlattenedEntitiesTransform] = None
    nested_entities_transform: Optional[NestedEntitiesTransform] = None


def transform_and_nest(
        flattened_entities: ExtractedEntitiesFlattened,
        config: Optional[EntitiesTransformConfig] = None
) -> ExtractedEntitiesNested:
    if config and config.flattened_entities_transform:
        flattened_entities = apply_flattened_entities_transform(
            flattened_entities,
            config.flattened_entities_transform
        )
    nested_entities = nest_entities(flattened_entities)
    if config and config.nested_entities_transform:
        nested_entities = apply_nested_entities_transform(
            nested_entities,
            config.nested_entities_transform
        )
    return nested_entities


def get_enriched_media_by_id(
        media_id: int,
        config: Optional[EntitiesTransformConfig] = None
) -> Optional[ExtractedEntitiesNested]:
    row = db.execute_query(
        """SELECT *
           FROM media
           WHERE id = %(id)s""",
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
    nested_entities = transform_and_nest(flattened_entities, config)
    return nested_entities


def get_enriched_post_by_id(
        post_id: int,
        config: Optional[EntitiesTransformConfig] = None
) -> Optional[ExtractedEntitiesNested]:
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
    nested_entities = transform_and_nest(flattened_entities, config)
    return nested_entities


def get_enriched_account_by_id(
        account_id: int,
        config: Optional[EntitiesTransformConfig] = None
) -> Optional[ExtractedEntitiesNested]:
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
    nested_entities = transform_and_nest(flattened_entities, config)
    return nested_entities


def get_enriched_archiving_session_by_id(
        session_id: int,
        config: Optional[EntitiesTransformConfig] = None
) -> Optional[ArchiveSessionWithEntities]:
    session = get_archiving_session_by_id(session_id)
    if session is None:
        return None
    account_rows = db.execute_query(
        """SELECT a.id, aa.url, aa.archive_session_id, aa.display_name, aa.bio
           FROM account_archive AS aa
                    LEFT JOIN account AS a ON aa.canonical_id = a.id
           WHERE archive_session_id = %(id)s
        """,
        {"id": session_id},
        return_type="rows"
    )
    post_rows = db.execute_query(
        """SELECT p.id, p.account_id, pa.url, pa.archive_session_id, pa.caption, pa.publication_date, pa.data
           FROM post_archive AS pa
                    LEFT JOIN post AS p ON pa.canonical_id = p.id
           WHERE archive_session_id = %(id)s
        """,
        {"id": session_id},
        return_type="rows"
    )
    media_rows = db.execute_query(
        """SELECT m.id, m.post_id, ma.url, ma.local_url, ma.archive_session_id, ma.media_type, ma.data
           FROM media_archive AS ma
                    LEFT JOIN media AS m ON ma.canonical_id = m.id
           WHERE archive_session_id = %(id)s
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
    nested_entities = transform_and_nest(flattened_entities, config)
    return ArchiveSessionWithEntities(
        session=session,
        entities=nested_entities
    )


def get_archiving_sessions_by_account_id(
        account_id: int,
) -> list[ArchiveSession]:
    # fetching all sessions in which at least one post from the account was archived
    # additional sessions in which only the account was archived are not included,
    # in order not to confuse users through the inclusions of content the account merely engaged with
    account = get_account_by_id(account_id)
    if account is None:
        return []
    posts = get_posts_by_accounts([account])
    if not posts or len(posts) == 0:
        return []
    post_ids = [p.id for p in posts]
    query_args = {f"post_id_{i}": f"{post_id}" for i, post_id in enumerate(post_ids)}
    query_in_clause = ', '.join([f"%(post_id_{i})s" for i in range(len(post_ids))])
    session_rows = db.execute_query(
        f"""SELECT DISTINCT a_s.*
            FROM archive_session AS a_s
            LEFT JOIN post_archive AS p_a ON a_s.id = p_a.archive_session_id
            WHERE p_a.canonical_id IN ({query_in_clause})
        """,
        query_args,
        return_type="rows"
    )
    return [ArchiveSession(**s) for s in session_rows]


def get_archiving_sessions_by_post_id(
        post_id: int,
) -> list[ArchiveSession]:
    post = get_post_by_id(post_id)
    if post is None:
        return []
    session_rows = db.execute_query(
        """SELECT a_s.*
            FROM archive_session AS a_s
            LEFT JOIN post_archive AS p_a ON a_s.id = p_a.archive_session_id
            WHERE p_a.canonical_id = %(post_id)s
        """,
        {"post_id": post_id},
        return_type="rows"
    )
    return [ArchiveSession(**s) for s in session_rows]


def get_archiving_sessions_by_media_id(
        media_id: int,
) -> list[ArchiveSession]:
    media = db.execute_query(
        """SELECT * FROM media WHERE id = %(id)s""",
        {"id": media_id},
        return_type="single_row"
    )
    if media is None:
        return []
    session_rows = db.execute_query(
        """SELECT a_s.*
            FROM archive_session AS a_s
            LEFT JOIN media_archive AS m_a ON a_s.id = m_a.archive_session_id
            WHERE m_a.canonical_id = %(media_id)s""",
        {"media_id": media_id},
        return_type="rows"
    )
    return [ArchiveSession(**s) for s in session_rows]
