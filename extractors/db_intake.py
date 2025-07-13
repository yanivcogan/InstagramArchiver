import json
from typing import Optional

import db
from extractors.entity_types import ExtractedEntitiesFlattened, Account, Post, Media
from extractors.reconcile_entities import reconcile_accounts, reconcile_posts, reconcile_media


def incorporate_structure_into_db(structure: ExtractedEntitiesFlattened):
    for account in structure.accounts:
        existing_account = get_existing_account(account.url)
        if existing_account:
            account = reconcile_accounts(account, existing_account)
            update = True
        else:
            update = False
        store_account(account, update)

    for post in structure.posts:
        existing_post = get_existing_post(post.url)
        if existing_post:
            post = reconcile_posts(post, existing_post)
            update = True
        else:
            update = False
        store_post(post, update)

    for media in structure.media:
        existing_media = get_existing_media(media.url)
        if existing_media:
            media = reconcile_media(media, existing_media)
            update = True
        else:
            update = False
        store_media(media, update)


def get_existing_account(url: str) -> Optional[Account]:
    account_row = db.execute_query(
        "SELECT * FROM account WHERE url=%(url)s",
        {"url": url},
        return_type="single_row"
    )
    if not account_row:
        return None
    account_row['data'] = json.loads(account_row['data']) if account_row['data'] else None
    account_row['notes'] = json.loads(account_row['notes']) if account_row['notes'] else []
    account_row['sheet_entries'] = json.loads(account_row['sheet_entries']) if account_row['sheet_entries'] else []
    return Account(**account_row)

def get_existing_post(url: str) -> Optional[Post]:
    post_row = db.execute_query(
        "SELECT * FROM post WHERE url=%(url)s",
        {"url": url},
        return_type="single_row"
    )
    if not post_row:
        return None
    post_row['data'] = json.loads(post_row['data']) if post_row['data'] else None
    post_row['notes'] = json.loads(post_row['notes']) if post_row['notes'] else []
    post_row['sheet_entries'] = json.loads(post_row['sheet_entries']) if post_row['sheet_entries'] else []
    return Post(**post_row)

def get_existing_media(url: str) -> Optional[Media]:
    media_row = db.execute_query(
        "SELECT * FROM media WHERE url=%(url)s",
        {"url": url},
        return_type="single_row"
    )
    if not media_row:
        return None
    media_row['data'] = json.loads(media_row['data']) if media_row['data'] else None
    media_row['sheet_entries'] = json.loads(media_row['sheet_entries']) if media_row['sheet_entries'] else []
    return Media(**media_row)


def store_account(account: Account, update: bool) -> bool:
    try:
        account.notes = account.notes or []
        account.notes = [note.strip() for note in account.notes if len(note.strip()) > 0]
        if update:
            db.execute_query(
                """UPDATE account
                   SET display_name  = %(display_name)s,
                       bio           = %(bio)s,
                       data          = %(data)s,
                       notes         = %(notes)s,
                       sheet_entries = %(sheet_entries)s
                   WHERE url = %(url)s""",
                {
                    "url": account.url,
                    "display_name": account.display_name,
                    "bio": account.bio,
                    "data": json.dumps(account.data) if account.data else None,
                    "notes": json.dumps(account.notes) if account.notes else "[]",
                    "sheet_entries": json.dumps(account.sheet_entries) if account.sheet_entries else "[]"
                },
                return_type="none"
            )
        else:
            db.execute_query(
                """INSERT INTO account (url, display_name, bio, data, notes, sheet_entries)
                   VALUES (%(url)s, %(display_name)s, %(bio)s, %(data)s, %(notes)s, %(sheet_entries)s)""",
                {
                    "url": account.url,
                    "display_name": account.display_name,
                    "bio": account.bio,
                    "data": json.dumps(account.data) if account.data else None,
                    "notes": json.dumps(account.notes) if account.notes else "[]",
                    "sheet_entries": json.dumps(account.sheet_entries) if account.sheet_entries else "[]"
                },
                return_type="none"
            )
        return True
    except Exception as e:
        print(f"Error storing account {account.url}: {e}")
        return False

def store_post(post: Post, update: bool) -> bool:
    try:
        post.notes = post.notes or []
        post.notes = [note.strip() for note in post.notes if len(note.strip()) > 0]
        if update:
            db.execute_query(
                """UPDATE post
                   SET account_url   = %(account_url)s,
                       publication_date = %(publication_date)s,
                       caption        = %(caption)s,
                       data           = %(data)s,
                       notes          = %(notes)s,
                       sheet_entries  = %(sheet_entries)s
                   WHERE url = %(url)s""",
                {
                    "url": post.url,
                    "account_url": post.account_url,
                    "publication_date": post.publication_date.isoformat() if post.publication_date else None,
                    "caption": post.caption,
                    "data": json.dumps(post.data) if post.data else None,
                    "notes": json.dumps(post.notes) if post.notes else "[]",
                    "sheet_entries": json.dumps(post.sheet_entries) if post.sheet_entries else "[]"
                },
                return_type="none"
            )
        else:
            db.execute_query(
                """INSERT INTO post (url, account_url, publication_date, caption, data, notes, sheet_entries)
                   VALUES (%(url)s, %(account_url)s, %(publication_date)s, %(caption)s, %(data)s, %(notes)s, %(sheet_entries)s)""",
                {
                    "url": post.url,
                    "account_url": post.account_url,
                    "publication_date": post.publication_date.isoformat() if post.publication_date else None,
                    "caption": post.caption,
                    "data": json.dumps(post.data) if post.data else None,
                    "notes": json.dumps(post.notes) if post.notes else "[]",
                    "sheet_entries": json.dumps(post.sheet_entries) if post.sheet_entries else "[]"
                },
                return_type="none"
            )
        return True
    except Exception as e:
        print(f"Error storing post {post.url}: {e}")
        return False

def store_media(media: Media, update: bool) -> bool:
    try:
        if update:
            db.execute_query(
                """UPDATE media
                   SET post_url     = %(post_url)s,
                       local_url   = %(local_url)s,
                       media_type  = %(media_type)s,
                       data        = %(data)s,
                       sheet_entries = %(sheet_entries)s
                   WHERE url = %(url)s""",
                {
                    "url": media.url,
                    "post_url": media.post_url,
                    "local_url": media.local_url,
                    "media_type": media.media_type,
                    "data": json.dumps(media.data) if media.data else None,
                    "sheet_entries": json.dumps(media.sheet_entries) if media.sheet_entries else "[]"
                },
                return_type="none"
            )
        else:
            db.execute_query(
                """INSERT INTO media (url, post_url, local_url, media_type, data, sheet_entries)
                   VALUES (%(url)s, %(post_url)s, %(local_url)s, %(media_type)s, %(data)s, %(sheet_entries)s)""",
                {
                    "url": media.url,
                    "post_url": media.post_url,
                    "local_url": media.local_url,
                    "media_type": media.media_type,
                    "data": json.dumps(media.data) if media.data else None,
                    "sheet_entries": json.dumps(media.sheet_entries) if media.sheet_entries else "[]"
                },
                return_type="none"
            )
        return True
    except Exception as e:
        print(f"Error storing media {media.url}: {e}")
        return False