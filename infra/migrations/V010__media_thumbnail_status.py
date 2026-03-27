import time


def run(cnx):
    cur = cnx.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'media'
              AND column_name = 'thumbnail_status'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            print("    drop FULLTEXT index on media (recreated at end) ...", flush=True)
            t = time.perf_counter()
            cur.execute("DROP INDEX search_idx_fulltext ON media")
            print(f"    dropped ({time.perf_counter() - t:.1f}s)")

            print("    add column thumbnail_status ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                ALTER TABLE media
                ADD COLUMN thumbnail_status
                    ENUM('pending', 'generated', 'not_needed', 'error')
                    NOT NULL DEFAULT 'pending'
                    AFTER thumbnail_path
            """)
            print(f"    add column done ({time.perf_counter() - t:.1f}s)")

            # Backfill from existing data
            # Already has a valid thumbnail path → generated
            print("    backfill: setting generated ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                UPDATE media
                SET thumbnail_status = 'generated'
                WHERE thumbnail_path IS NOT NULL
                  AND thumbnail_path NOT LIKE 'error:%'
            """)
            print(f"    backfill: generated — {cur.rowcount} rows ({time.perf_counter() - t:.1f}s)")

            # Previously failed thumbnail generation → error
            print("    backfill: setting error ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                UPDATE media
                SET thumbnail_status = 'error'
                WHERE thumbnail_path LIKE 'error:%'
            """)
            print(f"    backfill: error — {cur.rowcount} rows ({time.perf_counter() - t:.1f}s)")

            # No local file, or audio → not_needed (can never generate a thumbnail)
            print("    backfill: setting not_needed ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                UPDATE media
                SET thumbnail_status = 'not_needed'
                WHERE thumbnail_status = 'pending'
                  AND (local_url IS NULL OR media_type = 'audio')
            """)
            print(f"    backfill: not_needed — {cur.rowcount} rows ({time.perf_counter() - t:.1f}s)")
            # Everything else with a local file keeps the default 'pending'

            # Index for fast pending-thumbnail lookups
            print("    media_thumbnail_status_index: creating ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                CREATE INDEX media_thumbnail_status_index
                ON media (thumbnail_status)
            """)
            print(f"    media_thumbnail_status_index: done ({time.perf_counter() - t:.1f}s)")

            print("    recreate FULLTEXT index on media ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                CREATE FULLTEXT INDEX search_idx_fulltext
                    ON media (notes, annotation)
            """)
            print(f"    recreated ({time.perf_counter() - t:.1f}s)")

        cnx.commit()
    finally:
        cur.close()
