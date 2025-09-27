import json
from typing import Optional, TypeVar, Generic, Callable
from pydantic import BaseModel

import db
from extractors.entity_types import EntityBase, ExtractedEntitiesFlattened, Account, Post, Media
from extractors.reconcile_entities import reconcile_accounts, reconcile_posts, reconcile_media

EntityType = TypeVar("EntityType", bound="EntityBase")


class EntityProcessingConfig(BaseModel, Generic[EntityType]):
    key: str
    table: str
    data_type: type[EntityType]
    get_entity: Callable[[EntityType, Optional[int]], Optional[EntityType]]
    store_entity: Callable[[EntityType, bool, Optional[int]], int]
    merge: Callable[[EntityType, Optional[EntityType]], EntityType]


def incorporate_structure_into_db(structure: ExtractedEntitiesFlattened, archive_session_id: int) -> None:
    for entity_config in entity_types:
        entities: list = getattr(structure, entity_config.key, [])
        for entity in entities:
            existing_entity = entity_config.get_entity(entity, None)
            already_existed = existing_entity is not None
            entity_id = entity_config.store_entity(entity, already_existed, None)

            existing_entity_within_archive = entity_config.get_entity(existing_entity,
                                                                      archive_session_id) if existing_entity else None
            already_existed_within_archive = existing_entity_within_archive is not None
            existing_entity = entity_config.merge(entity, existing_entity)
            existing_entity_within_archive = entity_config.merge(entity, existing_entity_within_archive)


def get_stored_account_archive(account: Account, archive_session_id: Optional[int] = None) -> Optional[Account]:
    entry = db.execute_query(
        f'''SELECT * 
           FROM account{'_archive' if archive_session_id else ''}
           WHERE 
               ((url=%(url)s AND url IS NOT NULL) OR (id_on_platform=%(id_on_platform)s AND id_on_platform IS NOT NULL))
             {'AND archive_session_id=%(archive_session_id)s' if archive_session_id else ''}
        ''',
        {
            "url": account.url,
            "id_on_platform": account.id_on_platform,
            "archive_session_id": archive_session_id
        },
        return_type="single_row"
    )
    if not entry:
        return None
    return Account(**entry)


def get_stored_post_archive(post: Post, archive_session_id: Optional[int] = None) -> Optional[Post]:
    entry = db.execute_query(
        f'''SELECT * 
           FROM post{'_archive' if archive_session_id else ''}
           WHERE 
               ((url=%(url)s AND url IS NOT NULL) OR (id_on_platform=%(id_on_platform)s AND id_on_platform IS NOT NULL))
             {'AND archive_session_id=%(archive_session_id)s' if archive_session_id else ''}
        ''',
        {
            "url": post.url,
            "id_on_platform": post.id_on_platform,
            "archive_session_id": archive_session_id
        },
        return_type="single_row"
    )
    if not entry:
        return None
    return Post(**entry)


def get_stored_media_archive(media: Media, archive_session_id: Optional[int] = None) -> Optional[Media]:
    entry = db.execute_query(
        f'''SELECT * 
           FROM media{'_archive' if archive_session_id else ''}
           WHERE 
               ((url=%(url)s AND url IS NOT NULL) OR (id_on_platform=%(id_on_platform)s AND id_on_platform IS NOT NULL))
             {'AND archive_session_id=%(archive_session_id)s' if archive_session_id else ''}
        ''',
        {
            "url": media.url,
            "id_on_platform": media.id_on_platform,
            "archive_session_id": archive_session_id
        },
        return_type="single_row"
    )
    if not entry:
        return None
    return Media(**entry)


entity_types: list[EntityProcessingConfig] = [
    EntityProcessingConfig(
        key="accounts",
        table="account",
        data_type=Account,
        get_entity=get_stored_account_archive,
        merge=reconcile_accounts
    ),
    EntityProcessingConfig(
        key="posts",
        table="post",
        data_type=Post,
        get_entity=get_stored_post_archive,
        merge=reconcile_posts
    ),
    EntityProcessingConfig(
        key="media",
        table="media",
        data_type=Media,
        get_entity=get_stored_media_archive,
        merge=reconcile_media
    ),
]


def store_account(account: Account, update: bool, archive_session_id: int) -> int:
    try:
        if update:
            db.execute_query(
                """UPDATE account
                   SET display_name = %(display_name)s,
                       bio          = %(bio)s,
                       data         = %(data)s
                   WHERE url = %(url)s""",
                {
                    "url": account.url,
                    "display_name": account.display_name,
                    "bio": account.bio,
                    "data": json.dumps(account.data) if account.data else None,
                },
                return_type="none"
            )
        else:
            db.execute_query(
                """INSERT INTO account (url, display_name, bio, data)
                   VALUES (%(url)s, %(display_name)s, %(bio)s, %(data)s)""",
                {
                    "url": account.url,
                    "display_name": account.display_name,
                    "bio": account.bio,
                    "data": json.dumps(account.data) if account.data else None
                },
                return_type="none"
            )
        return True
    except Exception as e:
        print(f"Error storing account {account.url}: {e}")
        return False


def store_post(post: Post, update: bool, archive_session_id: int) -> int:
    try:
        if post.account_id is None:
            stored_account = get_stored_account_archive(
                Account(url=post.account_url, id_on_platform=post.account_id_on_platform), None
            )
            if stored_account is None:
                raise ValueError("Post must have account_id set before storing.")
            else:
                post.account_id = stored_account.id
        if update:
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
        else:
            db.execute_query(
                """INSERT INTO post (url, id_on_platform, account_id, publication_date, caption, data)
                   VALUES (%(url)s, %(id_on_platform)s, %(account_id)s, %(publication_date)s, %(caption)s, %(data)s)""",
                {
                    "url": post.url,
                    "id_on_platform": post.id_on_platform,
                    "account_id": post.account_id,
                    "publication_date": post.publication_date.isoformat() if post.publication_date else None,
                    "caption": post.caption,
                    "data": json.dumps(post.data) if post.data else None
                },
                return_type="none"
            )
        return True
    except Exception as e:
        print(f"Error storing post {post.url}: {e}")
        return False


def store_media(media: Media, update: bool, archive_session_id: int) -> int:
    try:
        if media.post_id is None:
            stored_post = get_stored_post_archive(
                Post(url=media.post_url, id_on_platform=media.post_id_on_platform), None
            )
            if stored_post is None:
                raise ValueError("Media must have post_id set before storing.")
            else:
                media.post_id = stored_post.id
        if update:
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
                    "data": json.dumps(media.data) if media.data else None
                },
                return_type="none"
            )
        else:
            db.execute_query(
                """INSERT INTO media (url, id_on_platform, post_id, local_url, media_type, data)
                   VALUES (%(url)s, %(id_on_platform)s, %(post_id)s, %(local_url)s, %(media_type)s, %(data)s)""",
                {
                    "url": media.url,
                    "id_on_platform": media.id_on_platform,
                    "post_id": media.post_id,
                    "local_url": media.local_url,
                    "media_type": media.media_type,
                    "data": json.dumps(media.data) if media.data else None
                },
                return_type="none"
            )
        return True
    except Exception as e:
        print(f"Error storing media {media.url}: {e}")
        return False
