import time


def run(cnx):
    cur = cnx.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'account'
              AND column_name = 'post_count'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            print("    drop FULLTEXT index on account (recreated at end) ...", flush=True)
            t = time.perf_counter()
            cur.execute("DROP INDEX idx_search_fulltext ON account")
            print(f"    dropped ({time.perf_counter() - t:.1f}s)")

            print("    add column post_count ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                ALTER TABLE account
                ADD COLUMN post_count INT NOT NULL DEFAULT 0
            """)
            print(f"    add column done ({time.perf_counter() - t:.1f}s)")

            # Populate counts for existing data
            print("    backfill post_count ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                UPDATE account a
                INNER JOIN (
                    SELECT account_id, COUNT(*) AS cnt
                    FROM post
                    WHERE account_id IS NOT NULL
                    GROUP BY account_id
                ) p ON a.id = p.account_id
                SET a.post_count = p.cnt
            """)
            print(f"    backfill done — {cur.rowcount} rows ({time.perf_counter() - t:.1f}s)")

            print("    recreate FULLTEXT index on account ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                CREATE FULLTEXT INDEX idx_search_fulltext
                    ON account (url, url_parts, display_name, bio, notes)
            """)
            print(f"    recreated ({time.perf_counter() - t:.1f}s)")

        # Add index on post_count if not present
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'account'
              AND index_name = 'account_post_count_index'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            print("    account_post_count_index: creating ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                CREATE INDEX account_post_count_index
                ON account (post_count)
            """)
            print(f"    account_post_count_index: done ({time.perf_counter() - t:.1f}s)")
        else:
            print("    account_post_count_index: already exists, skipping")

        cnx.commit()
    finally:
        cur.close()
