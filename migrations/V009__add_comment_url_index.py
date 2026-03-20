import time


def run(cnx):
    cur = cnx.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'comment'
              AND index_name = 'comment_url_index'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            print("    comment_url_index: creating ...", flush=True)
            t = time.perf_counter()
            cur.execute("CREATE INDEX comment_url_index ON comment (url(250))")
            print(f"    comment_url_index: done ({time.perf_counter() - t:.1f}s)")
        else:
            print("    comment_url_index: already exists, skipping")
    finally:
        cur.close()
