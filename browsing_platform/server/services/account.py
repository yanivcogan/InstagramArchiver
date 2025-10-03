from typing import Optional

import db
from browsing_platform.server.services.entities_hierarchy import nest_entities
from browsing_platform.server.services.media import get_media_by_posts
from browsing_platform.server.services.post import get_posts_by_accounts
from extractors.entity_types import Account, ExtractedEntitiesNested, ExtractedEntitiesFlattened


def get_account_by_id(account_id: int) -> Optional[Account]:
    account = db.execute_query(
        """SELECT * FROM account WHERE id LIKE %(id)s""",
        {"id": account_id},
        return_type="single_row"
    )
    if account is None:
        return None
    return Account(**account)


def get_enriched_account_by_id(account_id: int) -> Optional[ExtractedEntitiesNested]:
    account = get_account_by_id(account_id)
    if account is None:
        return None
    posts = get_posts_by_accounts([account])
    media = get_media_by_posts(posts)

    # Flatten and nest entities
    flattened_entities = ExtractedEntitiesFlattened(
        accounts=[account],
        posts=posts,
        media=media
    )
    nested_entities = nest_entities(flattened_entities)
    return nested_entities
