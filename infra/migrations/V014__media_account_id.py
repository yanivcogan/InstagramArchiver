import time


def run(cnx):
    cur = cnx.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'media'
              AND column_name = 'account_id'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            print("    drop FULLTEXT index on media (recreated at end) ...", flush=True)
            t = time.perf_counter()
            cur.execute("DROP INDEX search_idx_fulltext ON media")
            print(f"    dropped ({time.perf_counter() - t:.1f}s)")

            print("    add column account_id + FK ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                ALTER TABLE media
                ADD COLUMN account_id INT NULL,
                ADD CONSTRAINT media_account_id_fk
                    FOREIGN KEY (account_id) REFERENCES account (id)
            """)
            print(f"    add column done ({time.perf_counter() - t:.1f}s)")

            # Populate from associated post
            print("    backfill account_id from post ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                UPDATE media m
                INNER JOIN post p ON m.post_id = p.id
                SET m.account_id = p.account_id
            """)
            print(f"    backfill done — {cur.rowcount} rows ({time.perf_counter() - t:.1f}s)")

            print("    recreate FULLTEXT index on media ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                CREATE FULLTEXT INDEX search_idx_fulltext
                    ON media (notes, annotation)
            """)
            print(f"    recreated ({time.perf_counter() - t:.1f}s)")

        # Index for the FK / JOIN
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'media'
              AND index_name = 'media_account_id_index'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            print("    media_account_id_index: creating ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                CREATE INDEX media_account_id_index
                ON media (account_id)
            """)
            print(f"    media_account_id_index: done ({time.perf_counter() - t:.1f}s)")
        else:
            print("    media_account_id_index: already exists, skipping")

        cnx.commit()
    finally:
        cur.close()
