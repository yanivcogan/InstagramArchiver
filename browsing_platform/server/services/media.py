from typing import Optional

import db
from browsing_platform.server.services.account import get_account_by_id
from browsing_platform.server.services.entities_hierarchy import nest_entities
from browsing_platform.server.services.post import get_post_by_id
from extractors.entity_types import Post, Media, ExtractedEntitiesNested, ExtractedEntitiesFlattened


def get_media_by_id(media_id: int) -> Media | None:
    row = db.execute_query(
        """SELECT * FROM media WHERE id LIKE %(id)s""",
        {"id": media_id},
        return_type="single_row"
    )
    if row is None:
        return None
    return Media(**row)


def get_enriched_media_by_id(media_id: int) -> Optional[ExtractedEntitiesNested]:
    row = db.execute_query(
        """SELECT *
           FROM media
           WHERE id LIKE %(id)s""",
        {"id": media_id},
        return_type="single_row"
    )
    if row is None:
        return None

    media = Media(**row)
    post = get_post_by_id(media.post_id)
    account = get_account_by_id(post.account_id)

    # Flatten and nest entities
    flattened_entities = ExtractedEntitiesFlattened(
        accounts=[account],
        posts=[post],
        media=[media]
    )
    nested_entities = nest_entities(flattened_entities)
    return nested_entities

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
