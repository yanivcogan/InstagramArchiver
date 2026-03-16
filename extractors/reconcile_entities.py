import json
from datetime import datetime
from typing import Optional, Callable, TypeVar

from extractors.entity_types import Account, Post, Media

T = TypeVar('T')


def is_empty(value: Optional[any]) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, dict)):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip() == ""
    return False


def reconcile_primitives(a: Optional[any], b: Optional[any]) -> Optional[any]:
    """Return the first non-empty value; prefer a over b."""
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
    existing_account.id_on_platform = reconcile_primitives(existing_account.id_on_platform, new_account.id_on_platform)
    existing_account.url = reconcile_primitives(existing_account.url, new_account.url)
    existing_account.display_name = reconcile_primitives(existing_account.display_name, new_account.display_name)
    existing_account.bio = reconcile_primitives(existing_account.bio, new_account.bio)
    existing_account.data = reconcile_dicts(existing_account.data, new_account.data)
    return existing_account


def reconcile_posts(new_post: Post, existing_post: Optional[Post]) -> Post:
    if existing_post is None:
        return new_post
    existing_post.id_on_platform = reconcile_primitives(existing_post.id_on_platform, new_post.id_on_platform)
    existing_post.url = reconcile_primitives(existing_post.url, new_post.url)
    existing_post.account_url = reconcile_primitives(existing_post.account_url, new_post.account_url)
    existing_post.publication_date = reconcile_primitives(existing_post.publication_date, new_post.publication_date)
    existing_post.caption = reconcile_primitives(existing_post.caption, new_post.caption)
    existing_post.data = reconcile_dicts(existing_post.data, new_post.data)
    return existing_post


def reconcile_media(new_media: Media, existing_media: Optional[Media]) -> Media:
    if existing_media is None:
        return new_media
    existing_media.id_on_platform = reconcile_primitives(existing_media.id_on_platform, new_media.id_on_platform)
    existing_media.url = reconcile_primitives(existing_media.url, new_media.url)
    existing_media.post_url = reconcile_primitives(existing_media.post_url, new_media.post_url)
    existing_media.media_type = reconcile_primitives(existing_media.media_type, new_media.media_type)
    existing_media.data = reconcile_dicts(existing_media.data, new_media.data)
    return existing_media


def synthesize_from_archives(records: list[T], reconcile_fn: Callable[[T, T], T]) -> Optional[T]:
    """
    Fold a list of archive records into a single synthesized entity.

    Sorted oldest-first before folding so that first-non-empty wins semantics
    preserve the earliest observed value for each field (consistent with the
    pairwise merge used during initial ingestion).

    Returns None if records is empty.
    """
    if not records:
        return None
    sorted_records = sorted(records, key=lambda r: getattr(r, 'create_date', None) or datetime.min)
    result = sorted_records[0]
    for newer in sorted_records[1:]:
        result = reconcile_fn(newer, result)  # existing=result wins over newer
    return result
