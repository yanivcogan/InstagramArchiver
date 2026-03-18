import json
from typing import Any, Optional

from browsing_platform.server.services.annotation import Annotation
from extractors.entity_types import Account, Post
from utils import db


def post_exists(post_id: int) -> bool:
    return db.execute_query(
        "SELECT id FROM post WHERE id = %(id)s",
        {"id": post_id},
        return_type="single_row"
    ) is not None


def get_post_data_by_id(post_id: int) -> tuple[bool, Any]:
    """Returns (True, data) if the post exists, (False, None) if not found."""
    row = db.execute_query(
        "SELECT data FROM post WHERE id = %(id)s",
        {"id": post_id},
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


_POST_COLS = "id, id_on_platform, url, account_id, publication_date, caption, data, notes, create_date"
_POST_COLS_NO_DATA = "id, id_on_platform, url, account_id, publication_date, caption, NULL AS data, notes, create_date"


def get_post_by_id(post_id: int, include_data: bool = True) -> Optional[Post]:
    cols = _POST_COLS if include_data else _POST_COLS_NO_DATA
    row = db.execute_query(
        f"SELECT {cols} FROM post WHERE id = %(id)s",
        {"id": post_id},
        return_type="single_row"
    )
    if row is None:
        return None
    return Post(**row)


def get_posts_by_accounts(accounts: list[Account], include_data: bool = True) -> list[Post]:
    if not accounts or len(accounts) == 0:
        return []
    cols = _POST_COLS if include_data else _POST_COLS_NO_DATA
    query_args = {f"account_id_{i}": f"{account.id}" for i, account in enumerate(accounts)}
    query_in_clause = ', '.join([f"%(account_id_{i})s" for i in range(len(accounts))])
    posts = db.execute_query(
        f"""SELECT {cols} FROM post WHERE account_id IN ({query_in_clause})""",  # nosec B608 - query_in_clause contains only %(key)s placeholders, not user input
        query_args,
        return_type="rows"
    )
    return [Post(**p) for p in posts]

def annotate_post(post_id: int, annotation: Annotation) -> None:
    # Set notes field
    db.execute_query(
        """UPDATE post SET notes = %(notes)s WHERE id = %(id)s""",
        {"id": post_id, "notes": annotation.notes},
        return_type="none"
    )
    # Clear associated tags
    db.execute_query(
        """DELETE FROM post_tag WHERE post_id = %(id)s""",
        {"id": post_id},
        return_type="none"
    )
    # Add new tags
    for tag_id in annotation.tags:
        db.execute_query(
            """INSERT INTO post_tag (post_id, tag_id) VALUES (%(post_id)s, %(tag_id)s)""",
            {"post_id": post_id, "tag_id": tag_id},
            return_type="none"
        )