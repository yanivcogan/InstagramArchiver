def run(cnx):
    cur = cnx.cursor()
    try:
        # Add post_count column if not present
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'account'
              AND column_name = 'post_count'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            cur.execute("""
                ALTER TABLE account
                ADD COLUMN post_count INT NOT NULL DEFAULT 0
            """)
            # Populate counts for existing data
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

        # Add index on post_count if not present
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'account'
              AND index_name = 'account_post_count_index'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            cur.execute("""
                CREATE INDEX account_post_count_index
                ON account (post_count)
            """)

        cnx.commit()
    finally:
        cur.close()
