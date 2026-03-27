"""
V004 — allow null post url

Makes url nullable on post and post_archive.

The FULLTEXT index on post (notes, caption, url) is dropped before the ALTER
and recreated after, so MySQL can use ALGORITHM=INPLACE instead of COPY.
post_archive has no FULLTEXT index so needs no special handling.
"""

import time


def _index_exists(cur, table, index_name):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.statistics"
        " WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s",
        (table, index_name),
    )
    return cur.fetchone()[0] > 0


def run(cnx):
    cur = cnx.cursor()
    try:
        # Drop FULLTEXT before the ALTER so MySQL can use INPLACE instead of COPY.
        # Guarded so a retry after partial failure doesn't error on a missing index.
        if _index_exists(cur, "post", "idx_search_fulltext"):
            print("    drop FULLTEXT index on post (recreated at end) ...", flush=True)
            t = time.perf_counter()
            cur.execute("DROP INDEX idx_search_fulltext ON post")
            print(f"    dropped ({time.perf_counter() - t:.1f}s)")

        print("    post: MODIFY COLUMN url nullable ...", flush=True)
        t = time.perf_counter()
        cur.execute("ALTER TABLE post MODIFY COLUMN url VARCHAR(250) NULL")
        print(f"    post: done ({time.perf_counter() - t:.1f}s)")

        print("    post_archive: MODIFY COLUMN url nullable ...", flush=True)
        t = time.perf_counter()
        cur.execute("ALTER TABLE post_archive MODIFY COLUMN url VARCHAR(250) NULL")
        print(f"    post_archive: done ({time.perf_counter() - t:.1f}s)")

        if not _index_exists(cur, "post", "idx_search_fulltext"):
            print("    recreate FULLTEXT index on post ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                CREATE FULLTEXT INDEX idx_search_fulltext
                    ON post (notes, caption, url)
            """)
            print(f"    recreated ({time.perf_counter() - t:.1f}s)")

        cnx.commit()
    finally:
        cur.close()
