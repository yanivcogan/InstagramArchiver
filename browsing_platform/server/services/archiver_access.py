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
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

from browsing_platform.server.services import upload_service
from db_loaders.archiver_access_loader import ingest_into_account
from extractors.entity_types import Account
from utils import db

ArchiverAccessStatusValue = Literal["following", "requested", "followed_by", "follow_requests_from"]
ARCHIVER_ACCESS_STATUSES: tuple[ArchiverAccessStatusValue, ...] = (
    "following", "requested", "followed_by", "follow_requests_from",
)


class ArchiverAccessStatus(BaseModel):
    status: ArchiverAccessStatusValue
    observed_at: Optional[datetime] = None


class ArchiverAccessEntry(BaseModel):
    label: str
    statuses: list[ArchiverAccessStatus]


def get_archiver_access_for_url_suffixes(
        url_suffixes: list[str],
        platform: str = "instagram",
) -> dict[str, list[ArchiverAccessEntry]]:
    """Return, for every requested (lowercased) url_suffix, the full roster of
    registered archiver accounts, each carrying its relationship directions
    toward that target (empty statuses when there is no known relationship).

    One query, keyed on url_suffix (IN clause) with a LEFT JOIN from
    archiver_account so every registered archiver appears at least once; the
    distinct archivers in the result are therefore the full roster. Suffixes
    with no match get the roster with all-empty statuses.
    """
    suffixes = sorted({(s or "").strip().lower() for s in url_suffixes})
    if not suffixes:
        return {}

    suffix_args = {f"s_{i}": s for i, s in enumerate(suffixes)}
    in_clause = ", ".join(f"%(s_{i})s" for i in range(len(suffixes)))

    rows = db.execute_query(  # nosec B608 - in_clause contains only %(key)s placeholders
        f"""SELECT aa.label        AS label,
                   acc.target_url_suffix AS suffix,
                   acc.status      AS status,
                   acc.observed_at AS observed_at
            FROM archiver_account aa
            LEFT JOIN archiver_account_access acc
                   ON acc.archiver_account_id = aa.id
                  AND acc.platform = %(platform)s
                  AND acc.target_url_suffix IN ({in_clause})
            ORDER BY aa.label, aa.id""",
        {**suffix_args, "platform": platform},
        return_type="rows",
    ) or []

    # label is UNIQUE (uq_archiver_account_label), so the ordered-distinct labels
    # are the full roster; relationship statuses are keyed on (suffix, label).
    roster = list(dict.fromkeys(row["label"] for row in rows))
    matches: dict[tuple[str, str], list[ArchiverAccessStatus]] = {}
    for row in rows:
        if row["suffix"] is not None and row["status"] is not None:
            matches.setdefault((row["suffix"], row["label"]), []).append(
                ArchiverAccessStatus(status=row["status"], observed_at=row["observed_at"])
            )

    return {
        suffix: [
            ArchiverAccessEntry(label=label, statuses=matches.get((suffix, label), []))
            for label in roster
        ]
        for suffix in suffixes
    }


def get_archiver_access_for_account(account: Account) -> list[ArchiverAccessEntry]:
    """Return one entry per registered archiver account, each carrying the set of
    relationship directions that archiver holds toward the given target account
    (empty when there is no known relationship). Thin single-target wrapper over
    get_archiver_access_for_url_suffixes."""
    url_suffix = (account.url_suffix or "").strip().lower()
    platform = account.platform or "instagram"
    return get_archiver_access_for_url_suffixes([url_suffix], platform).get(url_suffix, [])


# ---------------------------------------------------------------------------
# Admin management (roster CRUD + export ingestion). Gated by auth_admin_access
# at the route layer. See routes/archiver_accounts.py.
# ---------------------------------------------------------------------------

class ArchiverAccountCounts(BaseModel):
    following: int = 0
    requested: int = 0
    followed_by: int = 0
    follow_requests_from: int = 0


class ArchiverAccountSummary(BaseModel):
    id: int
    label: str
    last_import_at: Optional[datetime] = None
    counts: ArchiverAccountCounts


def list_archiver_accounts_with_counts() -> list[ArchiverAccountSummary]:
    """One entry per registered archiver account, each with its per-status access
    counts (zero for statuses with no rows)."""
    rows = db.execute_query(
        """SELECT aa.id             AS id,
                  aa.label          AS label,
                  aa.last_import_at  AS last_import_at,
                  acc.status         AS status,
                  COUNT(acc.id)      AS cnt
           FROM archiver_account aa
           LEFT JOIN archiver_account_access acc ON acc.archiver_account_id = aa.id
           GROUP BY aa.id, aa.label, aa.last_import_at, acc.status
           ORDER BY aa.label, aa.id""",
        {},
        return_type="rows",
    ) or []

    # Insertion order matches the SQL ORDER BY, so the dict preserves it.
    summaries: dict[int, ArchiverAccountSummary] = {}
    for row in rows:
        aid = row["id"]
        summary = summaries.get(aid)
        if summary is None:
            summary = summaries[aid] = ArchiverAccountSummary(
                id=aid,
                label=row["label"],
                last_import_at=row["last_import_at"],
                counts=ArchiverAccountCounts(),
            )
        status = row["status"]
        if status in ARCHIVER_ACCESS_STATUSES:
            setattr(summary.counts, status, int(row["cnt"]))

    return list(summaries.values())


def get_archiver_account_row(archiver_account_id: int) -> Optional[dict]:
    return db.execute_query(
        "SELECT id, label, last_import_at FROM archiver_account WHERE id = %(id)s",
        {"id": archiver_account_id},
        return_type="single_row",
    )


def get_archiver_account_id_by_label(label: str) -> Optional[int]:
    row = db.execute_query(
        "SELECT id FROM archiver_account WHERE label = %(l)s",
        {"l": label},
        return_type="single_row",
    )
    return row["id"] if row else None


def insert_archiver_account(label: str) -> int:
    return db.execute_query(
        "INSERT INTO archiver_account (label) VALUES (%(l)s)",
        {"l": label},
        return_type="id",
    )


def update_archiver_account_label(archiver_account_id: int, label: str) -> None:
    db.execute_query(
        "UPDATE archiver_account SET label = %(l)s WHERE id = %(id)s",
        {"l": label, "id": archiver_account_id},
        return_type="none",
    )


def delete_archiver_account(archiver_account_id: int) -> None:
    # access rows cascade via the FK (ON DELETE CASCADE).
    db.execute_query(
        "DELETE FROM archiver_account WHERE id = %(id)s",
        {"id": archiver_account_id},
        return_type="none",
    )


def process_staged_export(archiver_account_id: int, staging_name: str) -> ArchiverAccountCounts:
    """Ingest a freshly-uploaded export staged under `staging_name`, rebuilding the
    archiver's access rows, then always delete the staged files. Reuses the shared
    upload staging area (see routes/upload.py TUS endpoints)."""
    if not upload_service.validate_archive_name(staging_name):
        raise ValueError("Invalid staging name")

    staging_dir = upload_service.get_staging_dir() / staging_name
    try:
        if not staging_dir.is_dir():
            raise FileNotFoundError(f"No staged upload found for {staging_name!r}")
        counts = ingest_into_account(archiver_account_id, Path(staging_dir))
    finally:
        upload_service.cleanup_staging_archive(staging_name)

    return ArchiverAccountCounts(**counts)
