import db
from extractors.entity_types import Account, Post


def get_posts_by_account(account: Account) -> list[Post]:
    post = db.execute_query(
        """SELECT * FROM post WHERE account_id LIKE %(account_id)s""",
        {"account_id": f"{account.id}%"},
        return_type="rows"
    )
    return [Post(**p) for p in post]