"""
V029 — Composite and covering indexes to support community detection queries.

community.py runs a large UNION ALL query over five tie-type tables. Each
sub-select already has a single-column index on the kernel-membership lookup
column, but without covering indexes MySQL must fetch the full row to retrieve
the second column needed for the SELECT or a post-join filter. For large
databases (hundreds of thousands of relations / interactions) these extra row
fetches are the dominant cost.

New indexes:

account_relation
  idx_ar_follower_type_followed  (follower_account_id, relation_type, followed_account_id)
    Direction-A follow/suggested: kernel lookup + relation_type filter + SELECT
    the followed_account_id — all from the index, no row fetch.
  idx_ar_followed_type_follower  (followed_account_id, relation_type, follower_account_id)
    Direction-B equivalent.

post_like
  idx_post_like_post_account  (post_id, account_id)
    Direction-A (kernel authored the liked post): join on post_id, then need
    pl.account_id for the SELECT — covered without a row fetch.
  idx_post_like_account_post  (account_id, post_id)
    Direction-B (kernel did the liking): scan on account_id, then need post_id
    for the JOIN post — covered without a row fetch.

comment
  idx_comment_post_account  (post_id, account_id)
    Direction-A: same pattern as post_like above.
  idx_comment_account_post  (account_id, post_id)
    Direction-B: same pattern as post_like above.

tagged_account
  After splitting the COALESCE sub-selects into four INNER JOIN sub-selects
  (V029 query change in community.py), each direction can use an index:

  idx_tagged_account_post_tagged   (post_id, tagged_account_id)
    Direction A-post: join from post side, SELECT tagged_account_id.
  idx_tagged_account_media_tagged  (media_id, tagged_account_id)
    Direction A-media: join from media side, SELECT tagged_account_id.
  idx_tagged_account_tagged_post   (tagged_account_id, post_id)
    Direction B-post: scan by tagged_account_id, need post_id for JOIN post.
  idx_tagged_account_tagged_media  (tagged_account_id, media_id)
    Direction B-media: scan by tagged_account_id, need media_id for JOIN media.
"""

import time

INDEXES = [
    # account_relation
    ("idx_ar_follower_type_followed", "account_relation",
     "follower_account_id, relation_type, followed_account_id", ""),
    ("idx_ar_followed_type_follower", "account_relation",
     "followed_account_id, relation_type, follower_account_id", ""),

    # post_like
    ("idx_post_like_post_account", "post_like", "post_id, account_id", ""),
    ("idx_post_like_account_post", "post_like", "account_id, post_id", ""),

    # comment
    ("idx_comment_post_account", "comment", "post_id, account_id", ""),
    ("idx_comment_account_post", "comment", "account_id, post_id", ""),

    # tagged_account
    ("idx_tagged_account_post_tagged",  "tagged_account", "post_id, tagged_account_id", ""),
    ("idx_tagged_account_media_tagged", "tagged_account", "media_id, tagged_account_id", ""),
    ("idx_tagged_account_tagged_post",  "tagged_account", "tagged_account_id, post_id", ""),
    ("idx_tagged_account_tagged_media", "tagged_account", "tagged_account_id, media_id", ""),
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
            prefix = f"CREATE {index_type} INDEX" if index_type else "CREATE INDEX"
            cur.execute(f"{prefix} {index_name} ON {table} ({columns})")
            print(f"    {index_name}: created ({time.perf_counter() - t:.1f}s)")
    cnx.commit()
    cur.close()
