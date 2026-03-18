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
            cur.execute("CREATE INDEX comment_url_index ON comment (url(250))")
    finally:
        cur.close()
