"""
V023 — Add indexes to the tag table for query performance:

  - idx_tag_quick_access   ON tag (quick_access)
      Speeds up the list_quick_access_tags query (WHERE quick_access = 1).

  - idx_tag_name_fulltext  ON tag (name, description)   [FULLTEXT]
      Enables efficient word-boundary matching for tag autocomplete.
      Currently the autocomplete uses LIKE '%query%' which forces a full
      table scan; a fulltext index supports faster IN BOOLEAN MODE searches
      as the tag table grows.

Each index is only created if it does not already exist.
"""

import time

INDEXES = [
    ("idx_tag_quick_access", "tag", "quick_access", ""),
    ("idx_tag_name_fulltext", "tag", "name, description", "FULLTEXT"),
]


def _index_exists(cur, table: str, index_name: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name   = %s
          AND index_name   = %s
        """,
        (table, index_name),
    )
    row = cur.fetchone()
    return (row["cnt"] if isinstance(row, dict) else row[0]) > 0


def run(cnx):
    cur = cnx.cursor(dictionary=True)
    for index_name, table, columns, index_type in INDEXES:
        if _index_exists(cur, table, index_name):
            print(f"    {index_name}: already exists, skipping")
        else:
            print(f"    {index_name}: creating ...", flush=True)
            t = time.perf_counter()
            cur.execute(f"CREATE {index_type} INDEX {index_name} ON {table} ({columns})")
            print(f"    {index_name}: created ({time.perf_counter() - t:.1f}s)")
    cnx.commit()
    cur.close()
