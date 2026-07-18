"""
Archiver Access Loader - Evidence Platform
==========================================

PURPOSE:
    Ingests Instagram "export my data" dumps for the operators' *archiving*
    accounts and builds the archiver_account / archiver_account_access index the
    browsing platform uses to show, next to a target account, which archiving
    account already follows it (has access) or has a pending follow request to it.

    See services/archiver_access.py (read path) and migration V047 (schema).

INPUT:
    An export-root directory containing:
      * manifest.json  — maps each anonymized export folder to its archiver's
        display label (the label is the archiver_account's identity):
            [ {"dir": "account_1", "label": "FLLF"}, ... ]
      * one subfolder per archiver (the "dir" above), each an unzipped Instagram
        data export with connections/followers_and_following/*.json.

    Four relationship files are parsed (each maps to a status; absent files are
    skipped). Two JSON schemas exist in the dump:
      following.json                        -> following            (relationships_following object; username in `title`)
      followers_*.json                      -> followed_by          (bare array; username in string_list_data[].value)
      pending_follow_requests.json          -> requested            (bare array; username in label_values[label=="Username"].value)
      follow_requests_you've_received.json  -> follow_requests_from (same label_values schema)

MATCHING:
    Exports carry usernames only (no pk). Usernames are case-insensitive, so they
    are stored lowercased and matched against LOWER(account.url_suffix) at read
    time. platform is fixed to 'instagram' (these exports are Instagram-specific).

SNAPSHOT SEMANTICS:
    Ingestion is a full per-archiver rebuild, NOT an upsert: each run deletes all
    of an archiver's existing access rows and reinserts the freshly-parsed set, so
    unfollows / withdrawn requests disappear. The archiver_account identity row
    itself is upserted by label (last_import_at refreshed).

USAGE:
    uv run db_loaders/archiver_access_loader.py <export_root>
    uv run db_loaders/archiver_access_loader.py <export_root> --dir account_1   # single archiver
"""
import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from utils import db

logger = logging.getLogger(__name__)

PLATFORM = "instagram"
RELATION_SUBDIR = Path("connections") / "followers_and_following"

# status -> the export file(s) that populate it + which schema parser to use.
FOLLOWING = "following"
REQUESTED = "requested"
FOLLOWED_BY = "followed_by"
FOLLOW_REQUESTS_FROM = "follow_requests_from"


def _to_datetime(ts: Optional[int]) -> Optional[datetime]:
    """Instagram export timestamps are unix seconds (UTC). Store as naive UTC."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError, OSError):
        return None


def _load_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not read %s: %s", path, e)
        return None


def _username_from_label_values(entry: dict) -> Optional[str]:
    for lv in entry.get("label_values") or []:
        if lv.get("label") == "Username":
            return lv.get("value")
    return None


def parse_following(data) -> list[tuple[str, Optional[int]]]:
    """following.json: object keyed relationships_following; username in `title`."""
    out: list[tuple[str, Optional[int]]] = []
    if not isinstance(data, dict):
        return out
    for entry in data.get("relationships_following") or []:
        username = entry.get("title")
        sld = entry.get("string_list_data") or []
        ts = sld[0].get("timestamp") if sld else None
        if username:
            out.append((username, ts))
    return out


def parse_string_list_array(data) -> list[tuple[str, Optional[int]]]:
    """followers_*.json: bare array; username in string_list_data[].value."""
    out: list[tuple[str, Optional[int]]] = []
    if not isinstance(data, list):
        return out
    for entry in data:
        sld = entry.get("string_list_data") or []
        if not sld:
            continue
        username = sld[0].get("value")
        ts = sld[0].get("timestamp")
        if username:
            out.append((username, ts))
    return out


def parse_label_values_array(data) -> list[tuple[str, Optional[int]]]:
    """pending_follow_requests / follow_requests_you've_received: bare array;
    username in label_values[label=="Username"].value; top-level timestamp."""
    out: list[tuple[str, Optional[int]]] = []
    if not isinstance(data, list):
        return out
    for entry in data:
        username = _username_from_label_values(entry)
        ts = entry.get("timestamp")
        if username:
            out.append((username, ts))
    return out


def find_relation_dir(root: Path) -> Optional[Path]:
    """Locate the connections/followers_and_following directory under `root`.

    The CLI passes an export folder with the relation subdir directly beneath it;
    the GUI-upload path stages the folder the admin picked, so the tree is nested
    one level deeper (`<root>/<picked-folder-name>/connections/...`). Try the
    direct location first, then search recursively for a `followers_and_following`
    directory whose parent is `connections`.
    """
    direct = root / RELATION_SUBDIR
    if direct.is_dir():
        return direct
    for candidate in root.rglob("followers_and_following"):
        if candidate.is_dir() and candidate.parent.name == "connections":
            return candidate
    return None


def collect_access_rows(relation_dir: Path) -> dict[str, dict[str, Optional[int]]]:
    """Parse all four relationship files under relation_dir.
    Returns {status: {lowercased_username: observed_ts}} — deduped within each
    status, keeping the most recent timestamp seen for that username."""
    result: dict[str, dict[str, Optional[int]]] = {
        FOLLOWING: {}, REQUESTED: {}, FOLLOWED_BY: {}, FOLLOW_REQUESTS_FROM: {},
    }

    def _merge(status: str, pairs: list[tuple[str, Optional[int]]]):
        bucket = result[status]
        for username, ts in pairs:
            key = username.strip().lower()
            if not key:
                continue
            existing = bucket.get(key)
            # keep the largest (most recent) timestamp; None sorts lowest
            if key not in bucket or (ts or 0) > (existing or 0):
                bucket[key] = ts

    _merge(FOLLOWING, parse_following(_load_json(relation_dir / "following.json")))
    _merge(REQUESTED, parse_label_values_array(_load_json(relation_dir / "pending_follow_requests.json")))
    _merge(FOLLOW_REQUESTS_FROM,
           parse_label_values_array(_load_json(relation_dir / "follow_requests_you've_received.json")))
    # followers can be paginated across followers_1.json, followers_2.json, ...
    for followers_file in sorted(relation_dir.glob("followers_*.json")):
        _merge(FOLLOWED_BY, parse_string_list_array(_load_json(followers_file)))

    return result


def upsert_archiver_account(label: str) -> int:
    """Insert or refresh the archiver_account identity row (keyed on label);
    return its id."""
    db.execute_query(
        """INSERT INTO archiver_account (label, last_import_at)
           VALUES (%(l)s, NOW())
           ON DUPLICATE KEY UPDATE last_import_at = NOW()""",
        {"l": label},
        return_type="none",
    )
    row = db.execute_query(
        "SELECT id FROM archiver_account WHERE label = %(l)s",
        {"l": label},
        return_type="single_row",
    )
    return row["id"]


def rebuild_archiver_access(archiver_account_id: int,
                            access: dict[str, dict[str, Optional[int]]]) -> dict[str, int]:
    """Full snapshot rebuild: delete all of this archiver's access rows, then
    insert the freshly-parsed set in a single transaction."""
    rows = []
    for status, bucket in access.items():
        for username, ts in bucket.items():
            rows.append((archiver_account_id, username, PLATFORM, status, _to_datetime(ts)))

    with db.transaction_batch():
        db.execute_query(
            "DELETE FROM archiver_account_access WHERE archiver_account_id = %(id)s",
            {"id": archiver_account_id},
            return_type="none",
        )
        if rows:
            db.batch_insert(
                "archiver_account_access",
                ["archiver_account_id", "target_url_suffix", "platform", "status", "observed_at"],
                rows,
            )

    return {status: len(bucket) for status, bucket in access.items()}


def ingest_into_account(archiver_account_id: int, export_root: Path) -> dict[str, int]:
    """Parse the export under `export_root` and rebuild `archiver_account_id`'s
    access rows from it (full snapshot). Refreshes last_import_at. Returns per-status
    counts. Raises FileNotFoundError if no connections/followers_and_following dir
    is found.

    Used by both the CLI (`load_export_root`) and the browsing-platform admin
    upload endpoint, which passes a freshly-staged upload directory.
    """
    relation_dir = find_relation_dir(export_root)
    if relation_dir is None:
        raise FileNotFoundError(
            f"No '{RELATION_SUBDIR}' directory found under {export_root}"
        )
    access = collect_access_rows(relation_dir)
    counts = rebuild_archiver_access(archiver_account_id, access)
    db.execute_query(
        "UPDATE archiver_account SET last_import_at = NOW() WHERE id = %(id)s",
        {"id": archiver_account_id},
        return_type="none",
    )
    return counts


def load_export_root(export_root: Path, only_dir: Optional[str] = None) -> None:
    manifest_path = export_root / "manifest.json"
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, list):
        raise SystemExit(f"manifest.json missing or malformed at {manifest_path} (expected a JSON array)")

    processed = 0
    for entry in manifest:
        dir_name = entry.get("dir")
        label = (entry.get("label") or "").strip()
        if not dir_name or not label:
            logger.warning("Skipping malformed manifest entry (needs dir + label): %r", entry)
            continue
        if only_dir and dir_name != only_dir:
            continue

        archiver_account_id = upsert_archiver_account(label)
        try:
            counts = ingest_into_account(archiver_account_id, export_root / dir_name)
        except FileNotFoundError:
            logger.warning("Skipping '%s' (%s): no %s directory", label, dir_name, RELATION_SUBDIR)
            continue
        processed += 1
        logger.info(
            "Imported '%s' (id=%s): following=%d requested=%d followed_by=%d follow_requests_from=%d",
            label, archiver_account_id,
            counts[FOLLOWING], counts[REQUESTED], counts[FOLLOWED_BY], counts[FOLLOW_REQUESTS_FROM],
        )

    logger.info("Done. Processed %d archiver account(s).", processed)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Ingest Instagram data-export dumps into the archiver-access index.")
    parser.add_argument("export_root", help="Directory containing manifest.json and per-archiver export folders")
    parser.add_argument("--dir", dest="only_dir", default=None,
                        help="Only import the manifest entry with this 'dir' (single archiver)")
    args = parser.parse_args()

    load_export_root(Path(args.export_root), only_dir=args.only_dir)


if __name__ == "__main__":
    main()
