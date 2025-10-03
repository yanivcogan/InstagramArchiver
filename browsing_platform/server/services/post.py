from typing import Optional

import db
from browsing_platform.server.services.account import get_account_by_id
from browsing_platform.server.services.entities_hierarchy import nest_entities
from browsing_platform.server.services.media import get_media_by_posts
from extractors.entity_types import Account, Post, ExtractedEntitiesNested, ExtractedEntitiesFlattened


def get_post_by_id(post_id: int) -> Post | None:
    row = db.execute_query(
        """SELECT * FROM post WHERE id LIKE %(id)s""",
        {"id": post_id},
        return_type="single_row"
    )
    if row is None:
        return None
    return Post(**row)


def get_enriched_post_by_id(post_id: int) -> Optional[ExtractedEntitiesNested]:
    post = get_post_by_id(post_id)
    if post is None:
        return None
    account = get_account_by_id(post.account_id)
    media = get_media_by_posts([post])

    # Flatten and nest entities
    flattened_entities = ExtractedEntitiesFlattened(
        accounts=[account],
        posts=[post],
        media=media
    )
    nested_entities = nest_entities(flattened_entities)
    return nested_entities


def get_posts_by_accounts(accounts: list[Account]) -> list[Post]:
    if not accounts or len(accounts) == 0:
        return []
    query_args = {f"account_id_{i}": f"{account.id}" for i, account in enumerate(accounts)}
    query_in_clause = ', '.join([f"%(account_id_{i})s" for i in range(len(accounts))])
    posts = db.execute_query(
        f"""SELECT * FROM post WHERE account_id IN ({query_in_clause})""",
        query_args,
        return_type="rows"
    )
    return [Post(**p) for p in posts]
