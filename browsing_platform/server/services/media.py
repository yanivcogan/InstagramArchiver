from typing import Optional

import db
from extractors.db_intake import ROOT_ARCHIVES, LOCAL_ARCHIVES_DIR_ALIAS
from extractors.entity_types import Post, Media
from extractors.thumbnail_generator import LOCAL_THUMBNAILS_DIR_ALIAS, ROOT_THUMBNAILS
from utils import ROOT_DIR


def get_media_by_id(media_id: int) -> Media | None:
    row = db.execute_query(
        """SELECT * FROM media WHERE id = %(id)s""",
        {"id": media_id},
        return_type="single_row"
    )
    if row is None:
        return None
    return Media(**row)


def get_media_by_posts(posts: list[Post]) -> list[Media]:
    if not posts or len(posts) == 0:
        return []
    query_args = {f"post_id_{i}": f"{post.id}" for i, post in enumerate(posts)}
    query_in_clause = ', '.join([f"%(post_id_{i})s" for i in range(len(posts))])
    media = db.execute_query(
        f"""SELECT * FROM media WHERE post_id IN ({query_in_clause})""",
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
