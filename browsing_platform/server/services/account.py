from typing import Optional

import db
from extractors.entity_types import Account


def get_account_by_id(account_id: int) -> Optional[Account]:
    account = db.execute_query(
        """SELECT * FROM account WHERE id LIKE %(id)s""",
        {"id": account_id},
        return_type="single_row"
    )
    if account is None:
        return None
    return Account(**account)