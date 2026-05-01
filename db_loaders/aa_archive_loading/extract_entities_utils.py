from typing import Optional
from urllib.parse import urlparse

import requests

from vt_titktok_map import vt_url_map
from entity_types import t_media_type
from archive_types import t_archive_types


def mime_to_media_type(mime_type: str) -> t_media_type:
    if mime_type.startswith("video/"):
        return "video"
    elif mime_type.startswith("audio/"):
        return "audio"
    elif mime_type.startswith("image/"):
        return "image"
    else:
        raise ValueError(f"Unsupported MIME type: {mime_type}")


def url_to_page_type(url: str) -> t_archive_types:
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path
    if "twitter.com" in domain or "x.com" in domain:
        if "status" in path:
            return "tweet"
    elif "youtube.com" in domain or "youtu.be" in domain:
        if "/watch" in path or "youtu.be" in domain:
            return "youtube video"
        elif "/channel" in path or "/c/" in path or "@" in path:
            return "youtube channel"
    elif "instagram.com" in domain:
        if ".com/p/" in url :
            return "insta post"
        elif ".com/reel/" in url :
            return "insta reel"
        elif ".com/highlights/" in url:
            return "insta highlights"
        elif ".com/stories/" in url:
            return "insta stories"
        else:
            return "insta profile"
    elif "tiktok.com" in domain:
        return "tiktok video"
    elif "facebook.com" in domain:
        if "/posts/" in path or "/videos/" in path:
            return "facebook post"
        else:
            return "facebook profile"
    raise ValueError(f"Unsupported URL: {url}")

def get_canonical_tiktok_video_url(url: str) -> str:
    if "vt.tiktok.com" in url or "vm.tiktok.com" in url:
        canonical_url = vt_url_map.get(url, None)
        if canonical_url is None:
            response = requests.head(url, allow_redirects=True)
            canonical_url = response.url
    else:
        canonical_url = url
    canonical_url = canonical_url.split("?")[0]
    canonical_url_parts = canonical_url.split("/")
    canonical_url = "/".join([p if "@" not in p else "@" for p in canonical_url_parts]) # replace @username with @
    return canonical_url

def get_tiktok_username_from_url(url: str) -> Optional[str]:
    try:
        suffix = url.split("@")[1]
        username = suffix.split("/")[0]
        return username
    except IndexError:
        return None



def retain_insta_content_id(entry_id: str) -> bool:
    omit_if_includes_any_of = ["profile_picture", "warc-file", "cover_media"]
    for term in omit_if_includes_any_of:
        if term in entry_id:
            return False
    return True


def get_insta_media_url_from_post_wrap(slide: dict) -> Optional[str]:
    insta_filename = None
    slide_metadata = slide.get("metadata", None)
    if slide_metadata and isinstance(slide_metadata, dict):
        insta_filename = slide_metadata.get("File Name", None)
    if not insta_filename:
        if "video_url" in slide.get("data", dict()):
            insta_filename = slide.get("data", dict()).get("video_url", "").split("?")[0].split("/")[-1]
        else:
            insta_filename = slide.get("data", dict()).get("thumbnail_url", "").split("?")[0].split("/")[-1]
    return insta_filename if insta_filename and len(insta_filename) > 0 else None

def remove_url_trailing_slash(url: str) -> str:
    if url.endswith('/'):
        return url[:-1]
    return url

def normalize_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    domains_keep_search_params = [
        "youtube.com", "youtu.be",
    ]
    parsed = urlparse(url)
    if not parsed.netloc in domains_keep_search_params:
        url = url.split("?")[0]
    url = remove_url_trailing_slash(url)
    return url

if __name__ == "__main__":
    # Example usage
    print(get_canonical_tiktok_video_url("https://vt.tiktok.com/ZS2HtLpsn/"))
    print(get_canonical_tiktok_video_url("https://www.tiktok.com/@adir_hazan_/video/7379224171324214535"))
