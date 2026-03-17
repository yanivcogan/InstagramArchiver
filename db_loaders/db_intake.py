import json
import logging
from pathlib import Path
from typing import Optional, TypeVar, Generic, Callable

from pydantic import BaseModel

from extractors.entity_types import EntityBase, ExtractedEntitiesFlattened, Account, Post, Media
from extractors.reconcile_entities import reconcile_accounts, reconcile_posts, reconcile_media, synthesize_from_archives, reconcile_primitives
from root_anchor import ROOT_DIR
from utils import db

logger = logging.getLogger(__name__)

LOCAL_ARCHIVES_DIR_ALIAS = 'local_archive_har'
ROOT_ARCHIVES = Path(ROOT_DIR) / "archives"
EntityType = TypeVar("EntityType", bound="EntityBase")


class EntityProcessingConfig(BaseModel, Generic[EntityType]):
    key: str
    table: str
    get_canonical: Callable[[EntityType], Optional[EntityType]]
    get_archive_record: Callable[[int, int], Optional[EntityType]]
    get_all_archives_for_canonical: Callable[[int], list[EntityType]]
    raw_entity_preprocessing: Optional[Callable[[EntityType, Optional[int], Optional[Path]], EntityType]] = None
    store_entity: Callable[[EntityType, Optional[EntityType], Optional[Path]], int]
    store_entity_archive: Callable[[EntityType, int, Optional[int], Optional[int], Optional[Path]], int]
    merge: Callable[[EntityType, Optional[EntityType]], EntityType]


def incorporate_structures_into_db(
        structures: ExtractedEntitiesFlattened,
        archive_session_id: int,
        archive_location: Optional[Path]
) -> None:
    """
    Process extracted entities and store them in the database.
    Creates both canonical records and archive-specific records for each entity.

    Re-processing safety: if an archive session is processed more than once, archive
    records for that session are updated in place (no duplicates). The canonical entity
    is then re-synthesized from ALL its archive records (oldest-first, first-non-empty
    wins). Identifier fields (id_on_platform, url) on the canonical are immutable once
    set — re-synthesis can fill them in but never clears them.
    """
    logger.debug(f"Incorporating structures into DB for archive session {archive_session_id}")

    with db.transaction_batch():
        for entity_config in entity_types:
            entities: list = getattr(structures, entity_config.key, [])

            # Posts without an id_on_platform cannot be identified or deduplicated.
            if entity_config.key == "posts":
                valid_entities = [e for e in entities if e.id_on_platform is not None]
                skipped = len(entities) - len(valid_entities)
                if skipped:
                    logger.warning(f"Skipping {skipped} post(s) with no id_on_platform")
                entities = valid_entities

            new_count = 0
            updated_count = 0
            logger.debug(f"Processing {len(entities)} {entity_config.key}")

            for entity in entities:
                existing_canonical = entity_config.get_canonical(entity)
                existing_canonical_id = existing_canonical.id if existing_canonical else None

                if entity_config.raw_entity_preprocessing is not None:
                    entity = entity_config.raw_entity_preprocessing(entity, existing_canonical_id, archive_location)

                if existing_canonical is None:
                    # First time this entity has been seen anywhere.
                    # Store the canonical directly from the extracted entity, then
                    # insert the archive record pointing back to it.
                    canonical_id = entity_config.store_entity(entity, None, archive_location)
                    archive_id = entity_config.store_entity_archive(
                        entity, archive_session_id, None, canonical_id, archive_location
                    )
                    entity.id = archive_id
                    new_count += 1
                else:
                    # Entity already exists in the canonical table.
                    # Upsert the archive record for this session, then re-synthesize
                    # the canonical from all its archive records.
                    existing_archive = entity_config.get_archive_record(existing_canonical_id, archive_session_id)
                    existing_archive_id = existing_archive.id if existing_archive else None

                    archive_entity = entity_config.merge(entity, existing_archive)
                    archive_entity.id = existing_archive_id
                    archive_entity.canonical_id = existing_canonical_id

                    archive_id = entity_config.store_entity_archive(
                        archive_entity, archive_session_id, existing_archive_id, existing_canonical_id, archive_location
                    )
                    entity.id = archive_id

                    all_archives = entity_config.get_all_archives_for_canonical(existing_canonical_id)
                    synthesized = synthesize_from_archives(all_archives, entity_config.merge)

                    # Identifier fields are immutable once set on the canonical —
                    # re-synthesis may fill them in but must never clear them.
                    _preserve_canonical_identifiers(synthesized, existing_canonical)
                    synthesized.id = existing_canonical_id

                    entity_config.store_entity(synthesized, existing_canonical, archive_location)
                    updated_count += 1

            logger.info(f"Processed {entity_config.key}: {new_count} new, {updated_count} updated")


def _preserve_canonical_identifiers(synthesized: EntityBase, existing_canonical: EntityBase) -> None:
    """
    Identifier fields on the canonical entity are used as stable external keys
    (e.g. in platform URLs) and must only grow, never shrink. Apply the same
    first-non-empty rule but always favouring the existing canonical value.
    """
    if hasattr(synthesized, 'id_on_platform'):
        synthesized.id_on_platform = reconcile_primitives(
            existing_canonical.id_on_platform, synthesized.id_on_platform
        )
    if hasattr(synthesized, 'url'):
        synthesized.url = reconcile_primitives(existing_canonical.url, synthesized.url)


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

def get_canonical_account(account: Account) -> Optional[Account]:
    entry = db.execute_query(
        """SELECT * FROM account
           WHERE (url = %(url)s AND url IS NOT NULL)
              OR (id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL)
           LIMIT 1""",
        {"url": account.url, "id_on_platform": account.id_on_platform},
        return_type="single_row"
    )
    return Account(**entry) if entry else None


def get_archive_record_account(canonical_id: int, archive_session_id: int) -> Optional[Account]:
    entry = db.execute_query(
        """SELECT * FROM account_archive
           WHERE canonical_id = %(canonical_id)s
             AND archive_session_id = %(archive_session_id)s""",
        {"canonical_id": canonical_id, "archive_session_id": archive_session_id},
        return_type="single_row"
    )
    return Account(**entry) if entry else None


def get_all_archives_for_canonical_account(canonical_id: int) -> list[Account]:
    entries = db.execute_query(
        "SELECT * FROM account_archive WHERE canonical_id = %(canonical_id)s",
        {"canonical_id": canonical_id},
        return_type="rows"
    )
    return [Account(**entry) for entry in (entries or [])]


def store_account(account: Account, existing_account: Optional[Account], _: Optional[Path]) -> int:
    account_identifiers: list[str] = (existing_account.identifiers if existing_account else None) or []
    if account.id_on_platform and f"id_{account.id_on_platform}" not in account_identifiers:
        account_identifiers.append(f"id_{account.id_on_platform}")
    if account.url and f"url_{account.url}" not in account_identifiers:
        account_identifiers.append(f"url_{account.url}")
    if existing_account is not None:
        db.execute_query(
            """UPDATE account
               SET url            = %(url)s,
                   id_on_platform = %(id_on_platform)s,
                   display_name   = %(display_name)s,
                   identifiers    = %(identifiers)s,
                   bio            = %(bio)s,
                   data           = %(data)s
               WHERE id = %(id)s""",
            {
                "id": account.id,
                "id_on_platform": account.id_on_platform,
                "url": account.url,
                "display_name": account.display_name,
                "bio": account.bio,
                "data": json.dumps(account.data) if account.data else None,
                "identifiers": json.dumps(account_identifiers),
            },
            return_type="none"
        )
        return account.id
    else:
        return db.execute_query(
            """INSERT INTO account (url, id_on_platform, identifiers, display_name, bio, data)
               VALUES (%(url)s, %(id_on_platform)s, %(identifiers)s, %(display_name)s, %(bio)s, %(data)s)""",
            {
                "id_on_platform": account.id_on_platform,
                "url": account.url,
                "display_name": account.display_name,
                "bio": account.bio,
                "data": json.dumps(account.data) if account.data else None,
                "identifiers": json.dumps(account_identifiers),
            },
            return_type="id"
        )


def store_account_archive(
        account: Account, archive_session_id: int, existing_id: Optional[int], canonical_id: Optional[int], _: Optional[Path]
) -> int:
    if existing_id is not None:
        db.execute_query(
            """UPDATE account_archive
               SET url                = %(url)s,
                   id_on_platform     = %(id_on_platform)s,
                   display_name       = %(display_name)s,
                   bio                = %(bio)s,
                   data               = %(data)s,
                   archive_session_id = %(archive_session_id)s,
                   canonical_id       = %(canonical_id)s
               WHERE id = %(id)s""",
            {
                "id": existing_id,
                "id_on_platform": account.id_on_platform,
                "url": account.url,
                "display_name": account.display_name,
                "bio": account.bio,
                "data": json.dumps(account.data) if account.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
            },
            return_type="none"
        )
        return existing_id
    else:
        return db.execute_query(
            """INSERT INTO account_archive (url, id_on_platform, display_name, bio, data, archive_session_id, canonical_id)
               VALUES (%(url)s, %(id_on_platform)s, %(display_name)s, %(bio)s, %(data)s, %(archive_session_id)s, %(canonical_id)s)""",
            {
                "id_on_platform": account.id_on_platform,
                "url": account.url,
                "display_name": account.display_name,
                "bio": account.bio,
                "data": json.dumps(account.data) if account.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
            },
            return_type="id"
        )


# ---------------------------------------------------------------------------
# Post
# ---------------------------------------------------------------------------

def get_canonical_post(post: Post) -> Optional[Post]:
    entry = db.execute_query(
        """SELECT * FROM post
           WHERE (url = %(url)s AND url IS NOT NULL)
              OR (id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL)
           LIMIT 1""",
        {"url": post.url, "id_on_platform": post.id_on_platform},
        return_type="single_row"
    )
    return Post(**entry) if entry else None


def get_archive_record_post(canonical_id: int, archive_session_id: int) -> Optional[Post]:
    entry = db.execute_query(
        """SELECT * FROM post_archive
           WHERE canonical_id = %(canonical_id)s
             AND archive_session_id = %(archive_session_id)s""",
        {"canonical_id": canonical_id, "archive_session_id": archive_session_id},
        return_type="single_row"
    )
    return Post(**entry) if entry else None


def get_all_archives_for_canonical_post(canonical_id: int) -> list[Post]:
    entries = db.execute_query(
        "SELECT * FROM post_archive WHERE canonical_id = %(canonical_id)s",
        {"canonical_id": canonical_id},
        return_type="rows"
    )
    return [Post(**entry) for entry in (entries or [])]


def store_post(post: Post, existing_post: Optional[Post], _: Optional[Path]) -> int:
    if post.account_id is None:
        stored_account = get_canonical_account(
            Account(url=post.account_url, id_on_platform=post.account_id_on_platform)
        )
        if stored_account is None:
            raise ValueError(f"Cannot store post {post.id_on_platform!r}: account not found "
                             f"(url={post.account_url!r}, id_on_platform={post.account_id_on_platform!r})")
        post.account_id = stored_account.id
    if existing_post is not None:
        db.execute_query(
            """UPDATE post
               SET url              = %(url)s,
                   id_on_platform   = %(id_on_platform)s,
                   account_id       = %(account_id)s,
                   publication_date = %(publication_date)s,
                   caption          = %(caption)s,
                   data             = %(data)s
               WHERE id = %(id)s""",
            {
                "id": post.id,
                "url": post.url,
                "id_on_platform": post.id_on_platform,
                "account_id": post.account_id,
                "publication_date": post.publication_date.isoformat() if post.publication_date else None,
                "caption": post.caption,
                "data": json.dumps(post.data) if post.data else None,
            },
            return_type="none"
        )
        return post.id
    else:
        return db.execute_query(
            """INSERT INTO post (url, id_on_platform, account_id, publication_date, caption, data)
               VALUES (%(url)s, %(id_on_platform)s, %(account_id)s, %(publication_date)s, %(caption)s, %(data)s)""",
            {
                "url": post.url,
                "id_on_platform": post.id_on_platform,
                "account_id": post.account_id,
                "publication_date": post.publication_date.isoformat() if post.publication_date else None,
                "caption": post.caption,
                "data": json.dumps(post.data) if post.data else None,
            },
            return_type="id"
        )


def store_post_archive(
        post: Post, archive_session_id: int, existing_id: Optional[int], canonical_id: Optional[int], _: Optional[Path]
) -> int:
    if existing_id is not None:
        db.execute_query(
            """UPDATE post_archive
               SET url                    = %(url)s,
                   id_on_platform         = %(id_on_platform)s,
                   publication_date       = %(publication_date)s,
                   caption                = %(caption)s,
                   data                   = %(data)s,
                   archive_session_id     = %(archive_session_id)s,
                   canonical_id           = %(canonical_id)s,
                   account_url            = %(account_url)s,
                   account_id_on_platform = %(account_id_on_platform)s
               WHERE id = %(id)s""",
            {
                "id": existing_id,
                "url": post.url,
                "id_on_platform": post.id_on_platform,
                "publication_date": post.publication_date.isoformat() if post.publication_date else None,
                "caption": post.caption,
                "data": json.dumps(post.data) if post.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
                "account_url": post.account_url,
                "account_id_on_platform": post.account_id_on_platform,
            },
            return_type="none"
        )
        return existing_id
    else:
        return db.execute_query(
            """INSERT INTO post_archive
                   (url, id_on_platform, publication_date, caption, data,
                    archive_session_id, canonical_id, account_url, account_id_on_platform)
               VALUES
                   (%(url)s, %(id_on_platform)s, %(publication_date)s, %(caption)s, %(data)s,
                    %(archive_session_id)s, %(canonical_id)s, %(account_url)s, %(account_id_on_platform)s)""",
            {
                "url": post.url,
                "id_on_platform": post.id_on_platform,
                "publication_date": post.publication_date.isoformat() if post.publication_date else None,
                "caption": post.caption,
                "data": json.dumps(post.data) if post.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
                "account_url": post.account_url,
                "account_id_on_platform": post.account_id_on_platform,
            },
            return_type="id"
        )


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------

def preprocess_media(media: Media, _: Optional[int], archive_location: Path) -> Media:
    local_url = (
        f"{LOCAL_ARCHIVES_DIR_ALIAS}/"
        + (archive_location / media.local_url).relative_to(ROOT_ARCHIVES).as_posix()
    ) if media.local_url is not None else None
    media.local_url = local_url
    return media


def get_canonical_media(media: Media) -> Optional[Media]:
    entry = db.execute_query(
        """SELECT * FROM media
           WHERE (url = %(url)s AND url IS NOT NULL)
              OR (id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL)
           LIMIT 1""",
        {"url": media.url, "id_on_platform": media.id_on_platform},
        return_type="single_row"
    )
    return Media(**entry) if entry else None


def get_archive_record_media(canonical_id: int, archive_session_id: int) -> Optional[Media]:
    entry = db.execute_query(
        """SELECT * FROM media_archive
           WHERE canonical_id = %(canonical_id)s
             AND archive_session_id = %(archive_session_id)s""",
        {"canonical_id": canonical_id, "archive_session_id": archive_session_id},
        return_type="single_row"
    )
    return Media(**entry) if entry else None


def get_all_archives_for_canonical_media(canonical_id: int) -> list[Media]:
    entries = db.execute_query(
        "SELECT * FROM media_archive WHERE canonical_id = %(canonical_id)s",
        {"canonical_id": canonical_id},
        return_type="rows"
    )
    return [Media(**entry) for entry in (entries or [])]


def store_media(media: Media, existing_media: Optional[Media], archive_location: Path) -> int:
    if media.post_id is None:
        stored_post = get_canonical_post(
            Post(url=media.post_url, id_on_platform=media.post_id_on_platform)
        )
        if stored_post is None:
            raise ValueError(f"Cannot store media {media.id_on_platform!r}: post not found "
                             f"(url={media.post_url!r}, id_on_platform={media.post_id_on_platform!r})")
        media.post_id = stored_post.id
    if existing_media is not None:
        db.execute_query(
            """UPDATE media
               SET url            = %(url)s,
                   id_on_platform = %(id_on_platform)s,
                   post_id        = %(post_id)s,
                   local_url      = %(local_url)s,
                   media_type     = %(media_type)s,
                   data           = %(data)s
               WHERE id = %(id)s""",
            {
                "id": media.id,
                "url": media.url,
                "id_on_platform": media.id_on_platform,
                "post_id": media.post_id,
                "local_url": media.local_url,
                "media_type": media.media_type,
                "data": json.dumps(media.data) if media.data else None,
            },
            return_type="none"
        )
        return media.id
    else:
        return db.execute_query(
            """INSERT INTO media (url, id_on_platform, post_id, local_url, media_type, data)
               VALUES (%(url)s, %(id_on_platform)s, %(post_id)s, %(local_url)s, %(media_type)s, %(data)s)""",
            {
                "url": media.url,
                "id_on_platform": media.id_on_platform,
                "post_id": media.post_id,
                "local_url": media.local_url,
                "media_type": media.media_type,
                "data": json.dumps(media.data) if media.data else None,
            },
            return_type="id"
        )


def store_media_archive(
        media: Media, archive_session_id: int, existing_id: Optional[int], canonical_id: Optional[int], archive_location: Path
) -> int:
    if existing_id is not None:
        db.execute_query(
            """UPDATE media_archive
               SET url                 = %(url)s,
                   id_on_platform      = %(id_on_platform)s,
                   local_url           = %(local_url)s,
                   media_type          = %(media_type)s,
                   data                = %(data)s,
                   archive_session_id  = %(archive_session_id)s,
                   canonical_id        = %(canonical_id)s,
                   post_url            = %(post_url)s,
                   post_id_on_platform = %(post_id_on_platform)s
               WHERE id = %(id)s""",
            {
                "id": existing_id,
                "url": media.url,
                "id_on_platform": media.id_on_platform,
                "local_url": media.local_url,
                "media_type": media.media_type,
                "data": json.dumps(media.data) if media.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
                "post_url": media.post_url,
                "post_id_on_platform": media.post_id_on_platform,
            },
            return_type="none"
        )
        return existing_id
    else:
        return db.execute_query(
            """INSERT INTO media_archive
                   (url, id_on_platform, local_url, media_type, data,
                    archive_session_id, canonical_id, post_url, post_id_on_platform)
               VALUES
                   (%(url)s, %(id_on_platform)s, %(local_url)s, %(media_type)s, %(data)s,
                    %(archive_session_id)s, %(canonical_id)s, %(post_url)s, %(post_id_on_platform)s)""",
            {
                "url": media.url,
                "id_on_platform": media.id_on_platform,
                "local_url": media.local_url,
                "media_type": media.media_type,
                "data": json.dumps(media.data) if media.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
                "post_url": media.post_url,
                "post_id_on_platform": media.post_id_on_platform,
            },
            return_type="id"
        )


# ---------------------------------------------------------------------------
# Entity processing registry
# ---------------------------------------------------------------------------

entity_types: list[EntityProcessingConfig] = [
    EntityProcessingConfig(
        key="accounts",
        table="account",
        get_canonical=get_canonical_account,
        get_archive_record=get_archive_record_account,
        get_all_archives_for_canonical=get_all_archives_for_canonical_account,
        store_entity=store_account,
        store_entity_archive=store_account_archive,
        merge=reconcile_accounts,
    ),
    EntityProcessingConfig(
        key="posts",
        table="post",
        get_canonical=get_canonical_post,
        get_archive_record=get_archive_record_post,
        get_all_archives_for_canonical=get_all_archives_for_canonical_post,
        store_entity=store_post,
        store_entity_archive=store_post_archive,
        merge=reconcile_posts,
    ),
    EntityProcessingConfig(
        key="media",
        table="media",
        get_canonical=get_canonical_media,
        get_archive_record=get_archive_record_media,
        get_all_archives_for_canonical=get_all_archives_for_canonical_media,
        store_entity=store_media,
        store_entity_archive=store_media_archive,
        merge=reconcile_media,
        raw_entity_preprocessing=preprocess_media,
    ),
]
