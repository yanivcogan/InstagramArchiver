import db
from extractors.entity_types import Post, Media


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
