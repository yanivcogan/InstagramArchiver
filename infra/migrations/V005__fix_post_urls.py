"""
Recompute the url column for every row in post and post_archive using the
same logic as the current extraction pipeline:

  - data.code present        →  https://www.instagram.com/p/{code}
  - data.product_type=='story'  →  NULL (cannot distinguish live stories from
                                   stored highlights in historical data; highlights
                                   require a collection ID that is not stored)
  - otherwise                →  leave the existing url unchanged

Rows are processed in batches of BATCH_SIZE to cap memory use regardless
of table size.
"""

import json
import time
from typing import Optional

BATCH_SIZE = 500


def _parse_data(raw) -> Optional[dict]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _new_url(data: dict, existing_url: Optional[str]) -> tuple[Optional[str], bool]:
    """
    Return (new_url, should_update).

    new_url may be None (correct stored value is NULL).
    should_update=False means the existing value is already correct / can't be improved.
    """
    code = data.get("code")
    product_type = (data.get("product_type") or "").lower()

    if code:
        return f"https://www.instagram.com/p/{code}", True

    if product_type == "story":
        # Cannot distinguish live stories from stored highlights in historical data;
        # highlights require a collection ID we don't have, so set all to NULL.
        if existing_url and "/p/" in existing_url:
            return None, True

    return None, False  # no improvement possible; leave unchanged


def _process_table(cnx, table: str, select_sql: str):
    """
    Iterate over `table` in batches, updating the url column where needed.
    `select_sql` must return columns: id, url, data.
    """
    write_cur = cnx.cursor()
    offset = 0
    total_updated = 0
    t_start = time.perf_counter()

    while True:
        read_cur = cnx.cursor(dictionary=True)
        read_cur.execute(f"{select_sql} ORDER BY id LIMIT %s OFFSET %s", (BATCH_SIZE, offset))
        rows = read_cur.fetchall()
        read_cur.close()

        if not rows:
            break

        for row in rows:
            data = _parse_data(row["data"])
            if not data:
                continue
            new, should_update = _new_url(data, row["url"])
            if should_update and new != row["url"]:
                write_cur.execute(
                    f"UPDATE {table} SET url = %s WHERE id = %s",
                    (new, row["id"]),
                )
                total_updated += 1

        offset += len(rows)
        if len(rows) < BATCH_SIZE:
            break

    write_cur.close()
    print(f"    [{table}] done — {total_updated} updated ({time.perf_counter() - t_start:.1f}s)", flush=True)
    return total_updated


def run(cnx):
    archive_updated = _process_table(
        cnx,
        table="post_archive",
        select_sql="SELECT id, url, data FROM post_archive",
    )

    post_updated = _process_table(
        cnx,
        table="post",
        select_sql="SELECT id, url, data FROM post",
    )

    print(f"    Done — post: {post_updated} updated, post_archive: {archive_updated} updated")
