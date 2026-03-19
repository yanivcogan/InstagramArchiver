import json
from typing import Any, Optional

from browsing_platform.server.services.annotation import Annotation
from extractors.entity_types import Post, Media
from utils import db


def media_exists(media_id: int) -> bool:
    return db.execute_query(
        "SELECT id FROM media WHERE id = %(id)s",
        {"id": media_id},
        return_type="single_row"
    ) is not None


def get_media_data_by_id(media_id: int) -> tuple[bool, Any]:
    """Returns (True, data) if the media exists, (False, None) if not found."""
    row = db.execute_query(
        "SELECT data FROM media WHERE id = %(id)s",
        {"id": media_id},
        return_type="single_row"
    )
    if row is None:
        return False, None
    data = row["data"]
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = None
    return True, data


_MEDIA_COLS = "id, id_on_platform, url, post_id, local_url, media_type, data, notes, annotation, thumbnail_path, thumbnail_status, create_date"
_MEDIA_COLS_NO_DATA = "id, id_on_platform, url, post_id, local_url, media_type, NULL AS data, notes, annotation, thumbnail_path, thumbnail_status, create_date"


def get_media_by_id(media_id: int, include_data: bool = True) -> Optional[Media]:
    cols = _MEDIA_COLS if include_data else _MEDIA_COLS_NO_DATA
    row = db.execute_query(
        f"SELECT {cols} FROM media WHERE id = %(id)s",
        {"id": media_id},
        return_type="single_row"
    )
    if row is None:
        return None
    return Media(**row)


def get_media_by_posts(posts: list[Post], include_data: bool = True) -> list[Media]:
    if not posts or len(posts) == 0:
        return []
    cols = _MEDIA_COLS if include_data else _MEDIA_COLS_NO_DATA
    query_args = {f"post_id_{i}": f"{post.id}" for i, post in enumerate(posts)}
    query_in_clause = ', '.join([f"%(post_id_{i})s" for i in range(len(posts))])
    media = db.execute_query(
        f"""SELECT {cols} FROM media WHERE post_id IN ({query_in_clause})""",  # nosec B608 - query_in_clause contains only %(key)s placeholders, not user input
        query_args,
        return_type="rows"
    )
    return [Media(**m) for m in media]


def get_media_thumbnail_path(thumbnail_path: str, local_url: str) -> Optional[str]:
    thumbnail_path = thumbnail_path or local_url
    if thumbnail_path is None:
        return None
    # if thumbnail_path.startswith(LOCAL_THUMBNAILS_DIR_ALIAS):
    #     thumbnail_path = thumbnail_path.replace(LOCAL_THUMBNAILS_DIR_ALIAS, ROOT_THUMBNAILS.relative_to(ROOT_DIR).as_posix())
    # elif thumbnail_path.startswith(LOCAL_ARCHIVES_DIR_ALIAS):
    #     thumbnail_path = thumbnail_path.replace(LOCAL_ARCHIVES_DIR_ALIAS, ROOT_ARCHIVES.relative_to(ROOT_DIR).as_posix())
    return thumbnail_path


def annotate_media(media_id: int, annotation: Annotation) -> None:
    # Set notes field
    db.execute_query(
        """UPDATE media SET notes = %(notes)s WHERE id = %(id)s""",
        {"id": media_id, "notes": annotation.notes},
        return_type="none"
    )
    # Clear associated tags
    db.execute_query(
        """DELETE FROM media_tag WHERE media_id = %(id)s""",
        {"id": media_id},
        return_type="none"
    )
    # Add new tags
    for tag_id in annotation.tags:
        db.execute_query(
            """INSERT INTO media_tag (media_id, tag_id) VALUES (%(media_id)s, %(tag_id)s)""",
            {"media_id": media_id, "tag_id": tag_id},
            return_type="none"
        )