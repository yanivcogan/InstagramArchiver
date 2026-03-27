import time


def run(cnx):
    cur = cnx.cursor()
    try:
        # Add publication_date column if not present
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'media'
              AND column_name = 'publication_date'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            print("    drop FULLTEXT index on media (recreated at end) ...", flush=True)
            t = time.perf_counter()
            cur.execute("DROP INDEX search_idx_fulltext ON media")
            print(f"    dropped ({time.perf_counter() - t:.1f}s)")

            print("    add column publication_date ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                ALTER TABLE media
                ADD COLUMN publication_date DATETIME NULL
            """)
            print(f"    add column done ({time.perf_counter() - t:.1f}s)")

            # Populate from associated post
            print("    backfill publication_date from post ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                UPDATE media m
                INNER JOIN post p ON m.post_id = p.id
                SET m.publication_date = p.publication_date
            """)
            print(f"    backfill done — {cur.rowcount} rows ({time.perf_counter() - t:.1f}s)")

            print("    recreate FULLTEXT index on media ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                CREATE FULLTEXT INDEX search_idx_fulltext
                    ON media (notes, annotation)
            """)
            print(f"    recreated ({time.perf_counter() - t:.1f}s)")

        # Regular B-tree index for range queries
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'media'
              AND index_name = 'media_publication_date_index'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            print("    media_publication_date_index: creating ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                CREATE INDEX media_publication_date_index
                ON media (publication_date)
            """)
            print(f"    media_publication_date_index: done ({time.perf_counter() - t:.1f}s)")
        else:
            print("    media_publication_date_index: already exists, skipping")

        # Functional index for DATE(publication_date) = DATE(val) equality checks
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'media'
              AND index_name = 'media_publication_date_date'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            print("    media_publication_date_date: creating ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                CREATE INDEX media_publication_date_date
                ON media ((DATE(publication_date)))
            """)
            print(f"    media_publication_date_date: done ({time.perf_counter() - t:.1f}s)")
        else:
            print("    media_publication_date_date: already exists, skipping")

        cnx.commit()
    finally:
        cur.close()
