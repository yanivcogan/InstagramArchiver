import time


def run(cnx):
    cur = cnx.cursor()
    try:
        # Functional index on DATE(publication_date) for post.
        # Allows the advanced-filter date equality check — DATE(`publication_date`) = DATE(val) —
        # to be sargable instead of requiring a full table scan.
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'post'
              AND index_name = 'post_publication_date_date'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            print("    post_publication_date_date: creating ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                CREATE INDEX post_publication_date_date
                ON post ((DATE(publication_date)))
            """)
            print(f"    post_publication_date_date: done ({time.perf_counter() - t:.1f}s)")
        else:
            print("    post_publication_date_date: already exists, skipping")

        # Functional index on DATE(archiving_timestamp) for archive_session.
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'archive_session'
              AND index_name = 'archive_session_archiving_date'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            print("    archive_session_archiving_date: creating ...", flush=True)
            t = time.perf_counter()
            cur.execute("""
                CREATE INDEX archive_session_archiving_date
                ON archive_session ((DATE(archiving_timestamp)))
            """)
            print(f"    archive_session_archiving_date: done ({time.perf_counter() - t:.1f}s)")
        else:
            print("    archive_session_archiving_date: already exists, skipping")

        cnx.commit()
    finally:
        cur.close()
