"""Archiver-account access index — which registered archiving accounts follow /
have requested (or are followed by / have follow requests from) a target account.

Sensitive data: reveals operators' account identities and social graph. The
route that exposes it is gated by services.permissions.auth_archiver_access.
Schema: migration V047.

Target identity is url_suffix + platform, matched case-insensitively (usernames
are case-insensitive; access rows are stored lowercased). url_suffix is
non-unique and recyclable, so this is a best-effort convenience signal, not an
identity assertion.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

from extractors.entity_types import Account
from utils import db

ArchiverAccessStatusValue = Literal["following", "requested", "followed_by", "follow_requests_from"]


class ArchiverAccessStatus(BaseModel):
    status: ArchiverAccessStatusValue
    observed_at: Optional[datetime] = None


class ArchiverAccessEntry(BaseModel):
    label: str
    statuses: list[ArchiverAccessStatus]


def get_archiver_access_for_account(account: Account) -> list[ArchiverAccessEntry]:
    """Return one entry per registered archiver account, each carrying the set of
    relationship directions that archiver holds toward the given target account
    (empty when there is no known relationship)."""
    url_suffix = (account.url_suffix or "").strip().lower()
    platform = account.platform or "instagram"

    rows = db.execute_query(
        """SELECT aa.id          AS archiver_account_id,
                  aa.label        AS label,
                  acc.status      AS status,
                  acc.observed_at AS observed_at
           FROM archiver_account aa
           LEFT JOIN archiver_account_access acc
                  ON acc.archiver_account_id = aa.id
                 AND acc.target_url_suffix = %(suffix)s
                 AND acc.platform = %(platform)s
           ORDER BY aa.label, aa.id""",
        {"suffix": url_suffix, "platform": platform},
        return_type="rows",
    ) or []

    # Dict preserves insertion order, which matches the SQL ORDER BY, so no
    # separate ordering list is needed.
    entries: dict[int, ArchiverAccessEntry] = {}
    for row in rows:
        aid = row["archiver_account_id"]
        entry = entries.get(aid)
        if entry is None:
            entry = entries[aid] = ArchiverAccessEntry(
                label=row["label"],
                statuses=[],
            )
        if row["status"] is not None:
            entry.statuses.append(
                ArchiverAccessStatus(status=row["status"], observed_at=row["observed_at"])
            )

    return list(entries.values())
