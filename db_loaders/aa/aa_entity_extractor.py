"""
AA Entity Extractor
===================
Converts a ParsedHTMLSummary (from aa_html_parser.py) into an ExtractedEntitiesFlattened
object that can be passed directly to db_intake.incorporate_structures_into_db().

Design note — multi-approach cascade pattern:
  The AA spreadsheet was built over a long period during which the tool's output format
  changed multiple times. For every piece of data we therefore maintain an ordered list of
  extraction attempts and take the first non-None result.  The cascade order always goes
  from newest/most-reliable format to oldest/fallback.

Currently only Instagram posts and reels are supported.
"""

import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from extractors.entity_types import Account, Post, Media, ExtractedEntitiesFlattened
from db_loaders.aa.aa_html_parser import ParsedHTMLSummary

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def _first(*values):
    """Return the first value in *values that is not None and not empty string."""
    for v in values:
        if v is not None and v != "" and v != "None":
            return v
    return None


def _safe_get(obj, *keys):
    """Safely traverse nested dict/list with a sequence of keys, returning None on any miss."""
    try:
        cur = obj
        for k in keys:
            if cur is None:
                return None
            cur = cur[k]
        return cur
    except (KeyError, IndexError, TypeError):
        return None


def _mime_to_media_type(mime_type: str) -> Optional[str]:
    if not mime_type:
        return None
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("audio/"):
        return "audio"
    if mime_type.startswith("image/"):
        return "image"
    return None


def _extract_url_suffix(full_url: Optional[str]) -> Optional[str]:
    """Strip scheme + host from a URL, leaving only the path (no leading slash, no trailing slash)."""
    if not full_url:
        return None
    parsed = urlparse(full_url)
    suffix = parsed.path.lstrip('/').rstrip('/')
    return suffix if suffix else None


def _to_full_cdn_url(raw: Optional[str], cdn_base: Optional[str]) -> Optional[str]:
    """
    Ensure *raw* is a full URL.
    - If it already starts with https?:// → return as-is.
    - Otherwise prepend cdn_base (scheme + netloc of the archive_location URL).
    - If cdn_base is also unavailable → return raw unchanged (best-effort).
    """
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if cdn_base:
        return cdn_base.rstrip('/') + '/' + raw.lstrip('/')
    return raw


def _get_instagram_cdn_filename(media_item: dict) -> Optional[str]:
    """
    Extract the Instagram CDN filename from a parsed media dict.
    Used to build a stable url_suffix for deduplication across different archive sources.

    Cascade:
      1. item["metadata"]["File Name"]  — most reliable, written by AA from exif/headers
      2. item["data"]["video_url"]       — raw CDN URL in data blob
      3. item["data"]["thumbnail_url"]   — thumbnail CDN URL
    """
    # Attempt 1: explicit File Name in metadata sub-dict
    filename = _safe_get(media_item, "metadata", "File Name")
    if filename:
        return filename

    # Attempt 2: video_url in data sub-dict
    video_url = _safe_get(media_item, "data", "video_url")
    if video_url:
        name = video_url.split("?")[0].split("/")[-1]
        if name:
            return name

    # Attempt 3: thumbnail_url in data sub-dict
    thumb_url = _safe_get(media_item, "data", "thumbnail_url")
    if thumb_url:
        name = thumb_url.split("?")[0].split("/")[-1]
        if name:
            return name

    return None


# ---------------------------------------------------------------------------
# Account extraction
# ---------------------------------------------------------------------------

def _extract_account(post_content: dict, metadata: dict) -> Optional[Account]:
    """
    Extract the post's author account using a multi-approach cascade.

    Format evolution (newest first):
      - metadata keys raw_data / post_data / reel_data / data contain a user sub-object
      - metadata["username"] + metadata["uploader_id"]  (yt-dlp sessions, circa 2024)
      - post_content["data"]["user"]                    (vanilla early format)
    """
    username_attempts = []
    id_on_platform_attempts = []
    display_name_attempts = []
    raw_data_attempts = []

    # Format A — newest: metadata raw_data / post_data / reel_data / data
    for key in ("raw_data", "post_data", "reel_data", "data"):
        blob = metadata.get(key)
        if isinstance(blob, dict):
            raw_data_attempts.append(blob)
            username_attempts.append(blob.get("username"))
            id_on_platform_attempts.append(blob.get("pk"))
            display_name_attempts.append(blob.get("full_name"))
            break  # use only the first non-None blob

    # Format B — yt-dlp sessions (metadata top-level channel/uploader_id fields)
    username_attempts.append(metadata.get("channel"))
    id_on_platform_attempts.append(metadata.get("uploader_id"))
    display_name_attempts.append(metadata.get("uploader"))
    raw_data_attempts.append({
        "channel": metadata.get("channel"),
        "uploader_id": metadata.get("uploader_id"),
        "uploader": metadata.get("uploader"),
    })

    # Format C — temporary fix period: flat username in metadata
    username_attempts.append(metadata.get("username"))

    # Format D — vanilla early format: user object inside post_content["data"]
    user_obj = _safe_get(post_content, "data", "user")
    if isinstance(user_obj, dict):
        username_attempts.append(user_obj.get("username"))
        id_on_platform_attempts.append(user_obj.get("pk"))
        display_name_attempts.append(user_obj.get("full_name"))
        raw_data_attempts.append(user_obj)

    username = _first(*username_attempts)
    id_on_platform = _first(*id_on_platform_attempts)
    display_name = _first(*display_name_attempts)
    raw_data = _first(*raw_data_attempts)

    if username is None and id_on_platform is None:
        logger.warning("Could not extract account username or id — no account will be created")
        return None

    url_suffix = username

    return Account(
        id_on_platform=str(id_on_platform) if id_on_platform is not None else None,
        url_suffix=url_suffix,
        platform='instagram',
        display_name=display_name,
        bio=None,
        data=raw_data,
    )


# ---------------------------------------------------------------------------
# Post extraction
# ---------------------------------------------------------------------------

def _extract_post(archived_url_suffix: str, metadata: dict, post_content: dict, account: Account) -> Optional[Post]:
    """
    Extract the post entity.

    The archived_url_suffix (e.g. "p/ABC123" or "reel/ABC123") is derived from the original
    spreadsheet URL — this is the authoritative source and avoids the reference-code bug where
    post_url was never assigned.

    Publication date cascade:
      1. metadata["timestamp"]        — most reliable ISO-like string
      2. metadata["entries"][0]["epoch"] — unix epoch fallback
    """
    post_url_suffix = archived_url_suffix  # already normalised during register step

    # Date cascade
    post_date: Optional[datetime] = None
    try:
        date_str = metadata["timestamp"]
        # AA writes timestamps as "2024-10-16 12:31:02+00:00" or "2024-10-16 12:31:02+0000"
        # Try a few known formats
        for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                post_date = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
    except (KeyError, TypeError):
        pass

    if post_date is None:
        try:
            epoch = metadata["entries"][0]["epoch"]
            post_date = datetime.fromtimestamp(int(epoch))
        except (KeyError, IndexError, TypeError, ValueError):
            pass

    # Normalise the URL suffix and extract post id_on_platform.
    # Instagram uses two URL formats for posts/reels:
    #   canonical:         "p/{shortcode}"  or  "reel/{shortcode}"
    #   username-prefixed: "{username}/p/{shortcode}"  or  "{username}/reel/{shortcode}"
    # The username-prefixed form is normalised to the canonical form so that the post
    # can be deduplicated against HAR/WACZ archives that use the canonical form.
    # URLs that match neither format (e.g. bare profile pages like "username") are not
    # posts and cannot be stored — return None so the caller skips this session.
    post_id_on_platform = None
    url_parts = post_url_suffix.split("/") if post_url_suffix else []
    if len(url_parts) >= 2 and url_parts[0] in ("p", "reel"):
        post_id_on_platform = url_parts[1]
    elif len(url_parts) >= 3 and url_parts[-2] in ("p", "reel"):
        post_id_on_platform = url_parts[-1]
        post_url_suffix = f"{url_parts[-2]}/{url_parts[-1]}"

    if post_id_on_platform is None:
        logger.warning(f"Cannot extract post id from URL suffix {post_url_suffix!r} — not a post URL")
        return None

    caption = metadata.get("title") or None

    return Post(
        id_on_platform=post_id_on_platform,
        url_suffix=post_url_suffix,
        platform='instagram',
        account_id_on_platform=account.id_on_platform,
        account_url_suffix=account.url_suffix,
        publication_date=post_date,
        caption=caption,
        data=post_content,
    )


# ---------------------------------------------------------------------------
# Media extraction
# ---------------------------------------------------------------------------

def _extract_media_list(post_url_suffix: str, structures: list[dict], cdn_base: Optional[str] = None) -> list[Media]:
    """
    Build the flat list of Media entities for a post.

    structures[0] is the primary media item; structures[0]["other media"] may be a list or
    dict containing carousel items.  All are flattened into a single list.
    """
    if not structures:
        return []

    post_content = structures[0]
    media_items: list[dict] = [post_content]

    other = post_content.get("other media")
    if isinstance(other, list):
        media_items.extend(other)
    elif isinstance(other, dict):
        media_items.append(other)

    media_list: list[Media] = []
    for item in media_items:
        mime_type = item.get("type", "")
        media_type = _mime_to_media_type(mime_type)
        if media_type is None:
            logger.warning(f"Skipping media item with unsupported MIME type: {mime_type!r}")
            continue

        # url_suffix: use the Instagram CDN filename if extractable (enables cross-source dedup)
        cdn_filename = _get_instagram_cdn_filename(item)
        url_suffix = cdn_filename if cdn_filename else None

        # local_url: full CDN URL of the archived copy.
        # _cdn_url (from HTML img/video src) is preferred; key is the bare storage path.
        # _to_full_cdn_url ensures a bare path is expanded to a full URL via cdn_base.
        raw_url = item.get("_cdn_url") or item.get("key") or None
        local_url = _to_full_cdn_url(raw_url, cdn_base)

        if url_suffix is None and local_url is None:
            logger.warning("Skipping media item: no url_suffix and no local_url extractable")
            continue

        media_list.append(Media(
            url_suffix=url_suffix,
            platform='instagram',
            post_url_suffix=post_url_suffix,
            local_url=local_url,
            media_type=media_type,
            data=item,
        ))

    return media_list


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_entities(
    archived_url_suffix: str,
    parsed: ParsedHTMLSummary,
    notes: Optional[str] = None,
    cdn_base: Optional[str] = None,
) -> Optional[ExtractedEntitiesFlattened]:
    """
    Convert a ParsedHTMLSummary into an ExtractedEntitiesFlattened ready for db_intake.

    Returns None if the minimum required data (account + post) could not be extracted.
    Logs a descriptive warning for each failed cascade so callers can diagnose format issues.
    """
    if not parsed.structures:
        logger.warning(f"No structures found in parsed summary for {archived_url_suffix!r}")
        return None

    post_content = parsed.structures[0]
    metadata = parsed.metadata

    account = _extract_account(post_content, metadata)
    if account is None:
        logger.warning(f"Could not extract account for {archived_url_suffix!r} — skipping")
        return None

    post = _extract_post(archived_url_suffix, metadata, post_content, account)
    if post is None:
        logger.warning(f"Could not extract post for {archived_url_suffix!r} — skipping")
        return None

    media = _extract_media_list(post.url_suffix, parsed.structures, cdn_base)
    if not media:
        logger.warning(f"No media extracted for {archived_url_suffix!r}")

    return ExtractedEntitiesFlattened(
        accounts=[account],
        posts=[post],
        media=media,
    )
