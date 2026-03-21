def run(cnx):
    cur = cnx.cursor()
    try:
        # Add account_id column if not present
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'media'
              AND column_name = 'account_id'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            cur.execute("""
                ALTER TABLE media
                ADD COLUMN account_id INT NULL,
                ADD CONSTRAINT media_account_id_fk
                    FOREIGN KEY (account_id) REFERENCES account (id)
            """)
            # Populate from associated post
            cur.execute("""
                UPDATE media m
                INNER JOIN post p ON m.post_id = p.id
                SET m.account_id = p.account_id
            """)

        # Index for the FK / JOIN
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'media'
              AND index_name = 'media_account_id_index'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            cur.execute("""
                CREATE INDEX media_account_id_index
                ON media (account_id)
            """)

        cnx.commit()
    finally:
        cur.close()
