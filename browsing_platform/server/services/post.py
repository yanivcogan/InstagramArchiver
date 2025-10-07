import db
from extractors.entity_types import Account, Post


def get_post_by_id(post_id: int) -> Post | None:
    row = db.execute_query(
        """SELECT * FROM post WHERE id = %(id)s""",
        {"id": post_id},
        return_type="single_row"
    )
    if row is None:
        return None
    return Post(**row)


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
