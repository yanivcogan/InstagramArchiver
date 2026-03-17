import json
import logging
from pathlib import Path
from typing import Optional, TypeVar, Generic, Callable

from pydantic import BaseModel

from extractors.entity_types import EntityBase, ExtractedEntitiesFlattened, Account, Post, Media, Comment, Like, TaggedAccount, AccountRelation
from extractors.reconcile_entities import reconcile_accounts, reconcile_posts, reconcile_media, reconcile_comments, reconcile_likes, reconcile_tagged_accounts, reconcile_account_relations, synthesize_from_archives, reconcile_primitives
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

            if entity_config.key in ("likes", "tagged_accounts", "account_relations"):
                valid_entities = [e for e in entities if e.id_on_platform is not None]
                skipped = len(entities) - len(valid_entities)
                if skipped:
                    logger.warning(f"Skipping {skipped} {entity_config.key} with no id_on_platform")
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
# Comment
# ---------------------------------------------------------------------------

def get_canonical_comment(comment: Comment) -> Optional[Comment]:
    entry = db.execute_query(
        """SELECT * FROM comment
           WHERE (id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL)
              OR (url = %(url)s AND url IS NOT NULL)
           LIMIT 1""",
        {"id_on_platform": comment.id_on_platform, "url": comment.url},
        return_type="single_row"
    )
    return Comment(**entry) if entry else None


def get_archive_record_comment(canonical_id: int, archive_session_id: int) -> Optional[Comment]:
    entry = db.execute_query(
        """SELECT * FROM comment_archive
           WHERE canonical_id = %(canonical_id)s
             AND archive_session_id = %(archive_session_id)s""",
        {"canonical_id": canonical_id, "archive_session_id": archive_session_id},
        return_type="single_row"
    )
    return Comment(**entry) if entry else None


def get_all_archives_for_canonical_comment(canonical_id: int) -> list[Comment]:
    entries = db.execute_query(
        "SELECT * FROM comment_archive WHERE canonical_id = %(canonical_id)s",
        {"canonical_id": canonical_id},
        return_type="rows"
    )
    return [Comment(**entry) for entry in (entries or [])]


def store_comment(comment: Comment, existing_comment: Optional[Comment], _: Optional[Path]) -> int:
    if comment.post_id is None and (comment.post_url or comment.post_id_on_platform):
        stored_post = get_canonical_post(Post(url=comment.post_url, id_on_platform=comment.post_id_on_platform))
        if stored_post is None:
            raise ValueError(f"Cannot store comment {comment.id_on_platform!r}: post not found "
                             f"(url={comment.post_url!r}, id_on_platform={comment.post_id_on_platform!r})")
        comment.post_id = stored_post.id
    if comment.account_id is None and comment.account_url:
        stored_account = db.execute_query(
            "SELECT id FROM account WHERE url = %(url)s LIMIT 1",
            {"url": comment.account_url},
            return_type="single_row"
        )
        if stored_account:
            comment.account_id = stored_account["id"]
    if comment.account_id is None and comment.account_id_on_platform:
        stored_account = db.execute_query(
            "SELECT id FROM account WHERE id_on_platform = %(id_on_platform)s LIMIT 1",
            {"id_on_platform": comment.account_id_on_platform},
            return_type="single_row"
        )
        if stored_account:
            comment.account_id = stored_account["id"]
    if existing_comment is not None:
        db.execute_query(
            """UPDATE comment
               SET id_on_platform                = %(id_on_platform)s,
                   url                           = %(url)s,
                   post_id                       = %(post_id)s,
                   account_id                    = %(account_id)s,
                   parent_comment_id_on_platform = %(parent_comment_id_on_platform)s,
                   text                          = %(text)s,
                   publication_date              = %(publication_date)s,
                   data                          = %(data)s
               WHERE id = %(id)s""",
            {
                "id": comment.id,
                "id_on_platform": comment.id_on_platform,
                "url": comment.url,
                "post_id": comment.post_id,
                "account_id": comment.account_id,
                "parent_comment_id_on_platform": comment.parent_comment_id_on_platform,
                "text": comment.text,
                "publication_date": comment.publication_date.isoformat() if comment.publication_date else None,
                "data": json.dumps(comment.data) if comment.data else None,
            },
            return_type="none"
        )
        return comment.id
    else:
        return db.execute_query(
            """INSERT INTO comment
                   (id_on_platform, url, post_id, account_id, parent_comment_id_on_platform,
                    text, publication_date, data)
               VALUES
                   (%(id_on_platform)s, %(url)s, %(post_id)s, %(account_id)s,
                    %(parent_comment_id_on_platform)s, %(text)s, %(publication_date)s, %(data)s)""",
            {
                "id_on_platform": comment.id_on_platform,
                "url": comment.url,
                "post_id": comment.post_id,
                "account_id": comment.account_id,
                "parent_comment_id_on_platform": comment.parent_comment_id_on_platform,
                "text": comment.text,
                "publication_date": comment.publication_date.isoformat() if comment.publication_date else None,
                "data": json.dumps(comment.data) if comment.data else None,
            },
            return_type="id"
        )


def store_comment_archive(
        comment: Comment, archive_session_id: int, existing_id: Optional[int], canonical_id: Optional[int], _: Optional[Path]
) -> int:
    if existing_id is not None:
        db.execute_query(
            """UPDATE comment_archive
               SET id_on_platform                = %(id_on_platform)s,
                   url                           = %(url)s,
                   post_url                      = %(post_url)s,
                   post_id_on_platform           = %(post_id_on_platform)s,
                   account_id_on_platform        = %(account_id_on_platform)s,
                   account_url                   = %(account_url)s,
                   parent_comment_id_on_platform = %(parent_comment_id_on_platform)s,
                   text                          = %(text)s,
                   publication_date              = %(publication_date)s,
                   data                          = %(data)s,
                   archive_session_id            = %(archive_session_id)s,
                   canonical_id                  = %(canonical_id)s
               WHERE id = %(id)s""",
            {
                "id": existing_id,
                "id_on_platform": comment.id_on_platform,
                "url": comment.url,
                "post_url": comment.post_url,
                "post_id_on_platform": comment.post_id_on_platform,
                "account_id_on_platform": comment.account_id_on_platform,
                "account_url": comment.account_url,
                "parent_comment_id_on_platform": comment.parent_comment_id_on_platform,
                "text": comment.text,
                "publication_date": comment.publication_date.isoformat() if comment.publication_date else None,
                "data": json.dumps(comment.data) if comment.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
            },
            return_type="none"
        )
        return existing_id
    else:
        return db.execute_query(
            """INSERT INTO comment_archive
                   (id_on_platform, url, post_url, post_id_on_platform, account_id_on_platform,
                    account_url, parent_comment_id_on_platform, text, publication_date, data,
                    archive_session_id, canonical_id)
               VALUES
                   (%(id_on_platform)s, %(url)s, %(post_url)s, %(post_id_on_platform)s,
                    %(account_id_on_platform)s, %(account_url)s, %(parent_comment_id_on_platform)s,
                    %(text)s, %(publication_date)s, %(data)s, %(archive_session_id)s, %(canonical_id)s)""",
            {
                "id_on_platform": comment.id_on_platform,
                "url": comment.url,
                "post_url": comment.post_url,
                "post_id_on_platform": comment.post_id_on_platform,
                "account_id_on_platform": comment.account_id_on_platform,
                "account_url": comment.account_url,
                "parent_comment_id_on_platform": comment.parent_comment_id_on_platform,
                "text": comment.text,
                "publication_date": comment.publication_date.isoformat() if comment.publication_date else None,
                "data": json.dumps(comment.data) if comment.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
            },
            return_type="id"
        )


# ---------------------------------------------------------------------------
# PostLike
# ---------------------------------------------------------------------------

def get_canonical_post_like(like: Like) -> Optional[Like]:
    if not like.id_on_platform:
        return None
    entry = db.execute_query(
        """SELECT * FROM post_like
           WHERE id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL
           LIMIT 1""",
        {"id_on_platform": like.id_on_platform},
        return_type="single_row"
    )
    return Like(**entry) if entry else None


def get_archive_record_post_like(canonical_id: int, archive_session_id: int) -> Optional[Like]:
    entry = db.execute_query(
        """SELECT * FROM post_like_archive
           WHERE canonical_id = %(canonical_id)s
             AND archive_session_id = %(archive_session_id)s""",
        {"canonical_id": canonical_id, "archive_session_id": archive_session_id},
        return_type="single_row"
    )
    return Like(**entry) if entry else None


def get_all_archives_for_canonical_post_like(canonical_id: int) -> list[Like]:
    entries = db.execute_query(
        "SELECT * FROM post_like_archive WHERE canonical_id = %(canonical_id)s",
        {"canonical_id": canonical_id},
        return_type="rows"
    )
    return [Like(**entry) for entry in (entries or [])]


def store_post_like(like: Like, existing_like: Optional[Like], _: Optional[Path]) -> int:
    if like.post_id is None and (like.post_url or like.post_id_on_platform):
        stored_post = get_canonical_post(Post(url=like.post_url, id_on_platform=like.post_id_on_platform))
        if stored_post is None:
            raise ValueError(f"Cannot store like {like.id_on_platform!r}: post not found "
                             f"(url={like.post_url!r}, id_on_platform={like.post_id_on_platform!r})")
        like.post_id = stored_post.id
    if like.account_id is None and like.account_url:
        stored_account = db.execute_query(
            "SELECT id FROM account WHERE url = %(url)s LIMIT 1",
            {"url": like.account_url},
            return_type="single_row"
        )
        if stored_account:
            like.account_id = stored_account["id"]
    if like.account_id is None and like.account_id_on_platform:
        stored_account = db.execute_query(
            "SELECT id FROM account WHERE id_on_platform = %(id_on_platform)s LIMIT 1",
            {"id_on_platform": like.account_id_on_platform},
            return_type="single_row"
        )
        if stored_account:
            like.account_id = stored_account["id"]
    if existing_like is not None:
        db.execute_query(
            """UPDATE post_like
               SET id_on_platform = %(id_on_platform)s,
                   post_id        = %(post_id)s,
                   account_id     = %(account_id)s,
                   data           = %(data)s
               WHERE id = %(id)s""",
            {
                "id": like.id,
                "id_on_platform": like.id_on_platform,
                "post_id": like.post_id,
                "account_id": like.account_id,
                "data": json.dumps(like.data) if like.data else None,
            },
            return_type="none"
        )
        return like.id
    else:
        return db.execute_query(
            """INSERT INTO post_like (id_on_platform, post_id, account_id, data)
               VALUES (%(id_on_platform)s, %(post_id)s, %(account_id)s, %(data)s)""",
            {
                "id_on_platform": like.id_on_platform,
                "post_id": like.post_id,
                "account_id": like.account_id,
                "data": json.dumps(like.data) if like.data else None,
            },
            return_type="id"
        )


def store_post_like_archive(
        like: Like, archive_session_id: int, existing_id: Optional[int], canonical_id: Optional[int], _: Optional[Path]
) -> int:
    if existing_id is not None:
        db.execute_query(
            """UPDATE post_like_archive
               SET id_on_platform         = %(id_on_platform)s,
                   post_id_on_platform    = %(post_id_on_platform)s,
                   post_url               = %(post_url)s,
                   account_id_on_platform = %(account_id_on_platform)s,
                   account_url            = %(account_url)s,
                   data                   = %(data)s,
                   archive_session_id     = %(archive_session_id)s,
                   canonical_id           = %(canonical_id)s
               WHERE id = %(id)s""",
            {
                "id": existing_id,
                "id_on_platform": like.id_on_platform,
                "post_id_on_platform": like.post_id_on_platform,
                "post_url": like.post_url,
                "account_id_on_platform": like.account_id_on_platform,
                "account_url": like.account_url,
                "data": json.dumps(like.data) if like.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
            },
            return_type="none"
        )
        return existing_id
    else:
        return db.execute_query(
            """INSERT INTO post_like_archive
                   (id_on_platform, post_id_on_platform, post_url, account_id_on_platform,
                    account_url, data, archive_session_id, canonical_id)
               VALUES
                   (%(id_on_platform)s, %(post_id_on_platform)s, %(post_url)s,
                    %(account_id_on_platform)s, %(account_url)s, %(data)s,
                    %(archive_session_id)s, %(canonical_id)s)""",
            {
                "id_on_platform": like.id_on_platform,
                "post_id_on_platform": like.post_id_on_platform,
                "post_url": like.post_url,
                "account_id_on_platform": like.account_id_on_platform,
                "account_url": like.account_url,
                "data": json.dumps(like.data) if like.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
            },
            return_type="id"
        )


# ---------------------------------------------------------------------------
# TaggedAccount
# ---------------------------------------------------------------------------

def get_canonical_tagged_account(ta: TaggedAccount) -> Optional[TaggedAccount]:
    if not ta.id_on_platform:
        return None
    entry = db.execute_query(
        """SELECT * FROM tagged_account
           WHERE id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL
           LIMIT 1""",
        {"id_on_platform": ta.id_on_platform},
        return_type="single_row"
    )
    return TaggedAccount(**entry) if entry else None


def get_archive_record_tagged_account(canonical_id: int, archive_session_id: int) -> Optional[TaggedAccount]:
    entry = db.execute_query(
        """SELECT * FROM tagged_account_archive
           WHERE canonical_id = %(canonical_id)s
             AND archive_session_id = %(archive_session_id)s""",
        {"canonical_id": canonical_id, "archive_session_id": archive_session_id},
        return_type="single_row"
    )
    return TaggedAccount(**entry) if entry else None


def get_all_archives_for_canonical_tagged_account(canonical_id: int) -> list[TaggedAccount]:
    entries = db.execute_query(
        "SELECT * FROM tagged_account_archive WHERE canonical_id = %(canonical_id)s",
        {"canonical_id": canonical_id},
        return_type="rows"
    )
    return [TaggedAccount(**entry) for entry in (entries or [])]


def store_tagged_account(ta: TaggedAccount, existing_ta: Optional[TaggedAccount], _: Optional[Path]) -> int:
    if ta.tagged_account_id is None and ta.tagged_account_url:
        stored_account = db.execute_query(
            "SELECT id FROM account WHERE url = %(url)s LIMIT 1",
            {"url": ta.tagged_account_url},
            return_type="single_row"
        )
        if stored_account:
            ta.tagged_account_id = stored_account["id"]
    if ta.tagged_account_id is None and ta.tagged_account_id_on_platform:
        stored_account = db.execute_query(
            "SELECT id FROM account WHERE id_on_platform = %(id_on_platform)s LIMIT 1",
            {"id_on_platform": ta.tagged_account_id_on_platform},
            return_type="single_row"
        )
        if stored_account:
            ta.tagged_account_id = stored_account["id"]
    if ta.post_id is None and (ta.context_post_url or ta.context_post_id_on_platform):
        stored_post = get_canonical_post(Post(url=ta.context_post_url, id_on_platform=ta.context_post_id_on_platform))
        if stored_post:
            ta.post_id = stored_post.id
    if ta.media_id is None and ta.context_media_url:
        stored_media = get_canonical_media(Media(url=ta.context_media_url, media_type="image"))
        if stored_media:
            ta.media_id = stored_media.id
    if existing_ta is not None:
        db.execute_query(
            """UPDATE tagged_account
               SET id_on_platform    = %(id_on_platform)s,
                   tagged_account_id = %(tagged_account_id)s,
                   post_id           = %(post_id)s,
                   media_id          = %(media_id)s,
                   tag_x_position    = %(tag_x_position)s,
                   tag_y_position    = %(tag_y_position)s,
                   data              = %(data)s
               WHERE id = %(id)s""",
            {
                "id": ta.id,
                "id_on_platform": ta.id_on_platform,
                "tagged_account_id": ta.tagged_account_id,
                "post_id": ta.post_id,
                "media_id": ta.media_id,
                "tag_x_position": ta.tag_x_position,
                "tag_y_position": ta.tag_y_position,
                "data": json.dumps(ta.data) if ta.data else None,
            },
            return_type="none"
        )
        return ta.id
    else:
        return db.execute_query(
            """INSERT INTO tagged_account
                   (id_on_platform, tagged_account_id, post_id, media_id,
                    tag_x_position, tag_y_position, data)
               VALUES
                   (%(id_on_platform)s, %(tagged_account_id)s, %(post_id)s, %(media_id)s,
                    %(tag_x_position)s, %(tag_y_position)s, %(data)s)""",
            {
                "id_on_platform": ta.id_on_platform,
                "tagged_account_id": ta.tagged_account_id,
                "post_id": ta.post_id,
                "media_id": ta.media_id,
                "tag_x_position": ta.tag_x_position,
                "tag_y_position": ta.tag_y_position,
                "data": json.dumps(ta.data) if ta.data else None,
            },
            return_type="id"
        )


def store_tagged_account_archive(
        ta: TaggedAccount, archive_session_id: int, existing_id: Optional[int], canonical_id: Optional[int], _: Optional[Path]
) -> int:
    if existing_id is not None:
        db.execute_query(
            """UPDATE tagged_account_archive
               SET id_on_platform                = %(id_on_platform)s,
                   tagged_account_id_on_platform = %(tagged_account_id_on_platform)s,
                   tagged_account_url            = %(tagged_account_url)s,
                   context_post_url              = %(context_post_url)s,
                   context_media_url             = %(context_media_url)s,
                   context_post_id_on_platform   = %(context_post_id_on_platform)s,
                   context_media_id_on_platform  = %(context_media_id_on_platform)s,
                   tag_x_position                = %(tag_x_position)s,
                   tag_y_position                = %(tag_y_position)s,
                   data                          = %(data)s,
                   archive_session_id            = %(archive_session_id)s,
                   canonical_id                  = %(canonical_id)s
               WHERE id = %(id)s""",
            {
                "id": existing_id,
                "id_on_platform": ta.id_on_platform,
                "tagged_account_id_on_platform": ta.tagged_account_id_on_platform,
                "tagged_account_url": ta.tagged_account_url,
                "context_post_url": ta.context_post_url,
                "context_media_url": ta.context_media_url,
                "context_post_id_on_platform": ta.context_post_id_on_platform,
                "context_media_id_on_platform": ta.context_media_id_on_platform,
                "tag_x_position": ta.tag_x_position,
                "tag_y_position": ta.tag_y_position,
                "data": json.dumps(ta.data) if ta.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
            },
            return_type="none"
        )
        return existing_id
    else:
        return db.execute_query(
            """INSERT INTO tagged_account_archive
                   (id_on_platform, tagged_account_id_on_platform, tagged_account_url,
                    context_post_url, context_media_url, context_post_id_on_platform,
                    context_media_id_on_platform, tag_x_position, tag_y_position, data,
                    archive_session_id, canonical_id)
               VALUES
                   (%(id_on_platform)s, %(tagged_account_id_on_platform)s, %(tagged_account_url)s,
                    %(context_post_url)s, %(context_media_url)s, %(context_post_id_on_platform)s,
                    %(context_media_id_on_platform)s, %(tag_x_position)s, %(tag_y_position)s, %(data)s,
                    %(archive_session_id)s, %(canonical_id)s)""",
            {
                "id_on_platform": ta.id_on_platform,
                "tagged_account_id_on_platform": ta.tagged_account_id_on_platform,
                "tagged_account_url": ta.tagged_account_url,
                "context_post_url": ta.context_post_url,
                "context_media_url": ta.context_media_url,
                "context_post_id_on_platform": ta.context_post_id_on_platform,
                "context_media_id_on_platform": ta.context_media_id_on_platform,
                "tag_x_position": ta.tag_x_position,
                "tag_y_position": ta.tag_y_position,
                "data": json.dumps(ta.data) if ta.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
            },
            return_type="id"
        )


# ---------------------------------------------------------------------------
# AccountRelation
# ---------------------------------------------------------------------------

def get_canonical_account_relation(ar: AccountRelation) -> Optional[AccountRelation]:
    if not ar.id_on_platform:
        return None
    entry = db.execute_query(
        """SELECT * FROM account_relation
           WHERE id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL
           LIMIT 1""",
        {"id_on_platform": ar.id_on_platform},
        return_type="single_row"
    )
    return AccountRelation(**entry) if entry else None


def get_archive_record_account_relation(canonical_id: int, archive_session_id: int) -> Optional[AccountRelation]:
    entry = db.execute_query(
        """SELECT * FROM account_relation_archive
           WHERE canonical_id = %(canonical_id)s
             AND archive_session_id = %(archive_session_id)s""",
        {"canonical_id": canonical_id, "archive_session_id": archive_session_id},
        return_type="single_row"
    )
    return AccountRelation(**entry) if entry else None


def get_all_archives_for_canonical_account_relation(canonical_id: int) -> list[AccountRelation]:
    entries = db.execute_query(
        "SELECT * FROM account_relation_archive WHERE canonical_id = %(canonical_id)s",
        {"canonical_id": canonical_id},
        return_type="rows"
    )
    return [AccountRelation(**entry) for entry in (entries or [])]


def _resolve_account_canonical_id(id_on_platform: Optional[str], url: Optional[str]) -> Optional[int]:
    if url:
        result = db.execute_query(
            "SELECT id FROM account WHERE url = %(url)s LIMIT 1",
            {"url": url},
            return_type="single_row"
        )
        if result:
            return result["id"]
    if id_on_platform:
        result = db.execute_query(
            "SELECT id FROM account WHERE id_on_platform = %(id_on_platform)s LIMIT 1",
            {"id_on_platform": id_on_platform},
            return_type="single_row"
        )
        if result:
            return result["id"]
    return None


def store_account_relation(ar: AccountRelation, existing_ar: Optional[AccountRelation], _: Optional[Path]) -> int:
    if ar.follower_account_id is None:
        ar.follower_account_id = _resolve_account_canonical_id(
            ar.follower_account_id_on_platform, ar.follower_account_url
        )
    if ar.followed_account_id is None:
        ar.followed_account_id = _resolve_account_canonical_id(
            ar.followed_account_id_on_platform, ar.followed_account_url
        )
    if ar.follower_account_id is None or ar.followed_account_id is None:
        raise ValueError(
            f"Cannot store account_relation {ar.id_on_platform!r}: "
            f"could not resolve account IDs (follower={ar.follower_account_id_on_platform!r}/{ar.follower_account_url!r}, "
            f"followed={ar.followed_account_id_on_platform!r}/{ar.followed_account_url!r})"
        )
    if existing_ar is not None:
        db.execute_query(
            """UPDATE account_relation
               SET follower_account_id = %(follower_account_id)s,
                   followed_account_id = %(followed_account_id)s,
                   relation_type       = %(relation_type)s,
                   id_on_platform      = %(id_on_platform)s,
                   data                = %(data)s
               WHERE id = %(id)s""",
            {
                "id": ar.id,
                "follower_account_id": ar.follower_account_id,
                "followed_account_id": ar.followed_account_id,
                "relation_type": ar.relation_type,
                "id_on_platform": ar.id_on_platform,
                "data": json.dumps(ar.data) if ar.data else None,
            },
            return_type="none"
        )
        return ar.id
    else:
        return db.execute_query(
            """INSERT INTO account_relation
                   (follower_account_id, followed_account_id, relation_type, id_on_platform, data)
               VALUES
                   (%(follower_account_id)s, %(followed_account_id)s, %(relation_type)s,
                    %(id_on_platform)s, %(data)s)""",
            {
                "follower_account_id": ar.follower_account_id,
                "followed_account_id": ar.followed_account_id,
                "relation_type": ar.relation_type,
                "id_on_platform": ar.id_on_platform,
                "data": json.dumps(ar.data) if ar.data else None,
            },
            return_type="id"
        )


def store_account_relation_archive(
        ar: AccountRelation, archive_session_id: int, existing_id: Optional[int], canonical_id: Optional[int], _: Optional[Path]
) -> int:
    if existing_id is not None:
        db.execute_query(
            """UPDATE account_relation_archive
               SET id_on_platform                  = %(id_on_platform)s,
                   follower_account_url             = %(follower_account_url)s,
                   follower_account_id_on_platform  = %(follower_account_id_on_platform)s,
                   followed_account_url             = %(followed_account_url)s,
                   followed_account_id_on_platform  = %(followed_account_id_on_platform)s,
                   relation_type                    = %(relation_type)s,
                   data                             = %(data)s,
                   archive_session_id               = %(archive_session_id)s,
                   canonical_id                     = %(canonical_id)s
               WHERE id = %(id)s""",
            {
                "id": existing_id,
                "id_on_platform": ar.id_on_platform,
                "follower_account_url": ar.follower_account_url,
                "follower_account_id_on_platform": ar.follower_account_id_on_platform,
                "followed_account_url": ar.followed_account_url,
                "followed_account_id_on_platform": ar.followed_account_id_on_platform,
                "relation_type": ar.relation_type,
                "data": json.dumps(ar.data) if ar.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
            },
            return_type="none"
        )
        return existing_id
    else:
        return db.execute_query(
            """INSERT INTO account_relation_archive
                   (id_on_platform, follower_account_url, follower_account_id_on_platform,
                    followed_account_url, followed_account_id_on_platform, relation_type,
                    data, archive_session_id, canonical_id)
               VALUES
                   (%(id_on_platform)s, %(follower_account_url)s, %(follower_account_id_on_platform)s,
                    %(followed_account_url)s, %(followed_account_id_on_platform)s, %(relation_type)s,
                    %(data)s, %(archive_session_id)s, %(canonical_id)s)""",
            {
                "id_on_platform": ar.id_on_platform,
                "follower_account_url": ar.follower_account_url,
                "follower_account_id_on_platform": ar.follower_account_id_on_platform,
                "followed_account_url": ar.followed_account_url,
                "followed_account_id_on_platform": ar.followed_account_id_on_platform,
                "relation_type": ar.relation_type,
                "data": json.dumps(ar.data) if ar.data else None,
                "archive_session_id": archive_session_id,
                "canonical_id": canonical_id,
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
