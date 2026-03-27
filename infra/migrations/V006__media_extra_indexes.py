"""
Add three indexes to the media table that exist in the target schema
but were never added to existing databases:

  - media_local_url_index     ON media (local_url)
  - media_media_type_index    ON media (media_type)
  - media_thumbnail_path_index ON media (thumbnail_path)

Each index is only created if it does not already exist, so this
migration is safe to run on databases that were built from the
up-to-date create_db.sql.
"""

import time

INDEXES = [
    ("media_local_url_index",      "media", "local_url"),
    ("media_media_type_index",     "media", "media_type"),
    ("media_thumbnail_path_index", "media", "thumbnail_path"),
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
    for index_name, table, column in INDEXES:
        if _index_exists(cur, table, index_name):
            print(f"    {index_name}: already exists, skipping")
        else:
            print(f"    {index_name}: creating ...", flush=True)
            t = time.perf_counter()
            cur.execute(f"CREATE INDEX {index_name} ON {table} ({column})")
            print(f"    {index_name}: created ({time.perf_counter() - t:.1f}s)")
    cur.close()
