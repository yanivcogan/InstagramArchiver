import json
from typing import Optional

from extractors.entity_types import Account, Post, Media


def is_empty(value: Optional[any]) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, dict)):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip() == ""
    return False


def reconcile_primitives(a: Optional[any], b: Optional[any]) -> Optional[any]:
    is_empty_a = is_empty(a)
    is_empty_b = is_empty(b)
    if is_empty_a and is_empty_b:
        return None
    if is_empty_a:
        return b
    if is_empty_b:
        return a
    return a


def reconcile_lists(a: Optional[list], b: Optional[list]) -> Optional[list]:
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    seen = set()
    result = []
    for item in a + b:
        try:
            key = json.dumps(item, default=str, sort_keys=True)
        except Exception:
            key = None  # Unserializable, treat as unique
        if key is not None:
            if key not in seen:
                seen.add(key)
                result.append(item)
        else:
            result.append(item)
    return result


def reconcile_dicts(a: Optional[dict], b: Optional[dict]) -> Optional[dict]:
    if a is None and b is None:
        return {}
    if a is None:
        return b
    if b is None:
        return a
    result = a.copy()
    for key, value in b.items():
        if key in result:
            if isinstance(result[key], list) and isinstance(value, list):
                result[key] = reconcile_lists(result[key], value)
            elif isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = reconcile_dicts(result[key], value)
            else:
                result[key] = reconcile_primitives(result[key], value)
        else:
            result[key] = value
    return result


def reconcile_accounts(new_account: Account, existing_account: Optional[Account]) -> Account:
    if existing_account is None:
        return new_account
    existing_account.data = reconcile_dicts(existing_account.data, new_account.data)
    existing_account.display_name = reconcile_primitives(existing_account.display_name, new_account.display_name)
    existing_account.bio = reconcile_primitives(existing_account.bio, new_account.bio)
    existing_account.notes = reconcile_lists(existing_account.notes, new_account.notes)
    existing_account.sheet_entries = reconcile_lists(existing_account.sheet_entries, new_account.sheet_entries)
    return existing_account


def reconcile_posts(new_post: Post, existing_post: Optional[Post]) -> Post:
    if existing_post is None:
        return new_post
    existing_post.account_url = reconcile_primitives(existing_post.account_url, new_post.account_url)
    existing_post.data = reconcile_dicts(existing_post.data, new_post.data)
    existing_post.publication_date = reconcile_primitives(existing_post.publication_date, new_post.publication_date)
    existing_post.caption = reconcile_primitives(existing_post.caption, new_post.caption)
    existing_post.notes = reconcile_lists(existing_post.notes, new_post.notes)
    existing_post.sheet_entries = reconcile_lists(existing_post.sheet_entries, new_post.sheet_entries)
    return existing_post


def reconcile_media(new_media: Media, existing_media: Optional[Media]) -> Media:
    if existing_media is None:
        return new_media
    existing_media.post_url = reconcile_primitives(existing_media.post_url, new_media.post_url)
    existing_media.data = reconcile_dicts(existing_media.data, new_media.data)
    existing_media.media_type = reconcile_primitives(existing_media.media_type, new_media.media_type)
    existing_media.sheet_entries = reconcile_lists(existing_media.sheet_entries, new_media.sheet_entries)
    return existing_media
