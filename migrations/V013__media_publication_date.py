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
            cur.execute("""
                ALTER TABLE media
                ADD COLUMN publication_date DATETIME NULL
            """)
            # Populate from associated post
            cur.execute("""
                UPDATE media m
                INNER JOIN post p ON m.post_id = p.id
                SET m.publication_date = p.publication_date
            """)

        # Regular B-tree index for range queries
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'media'
              AND index_name = 'media_publication_date_index'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            cur.execute("""
                CREATE INDEX media_publication_date_index
                ON media (publication_date)
            """)

        # Functional index for DATE(publication_date) = DATE(val) equality checks
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'media'
              AND index_name = 'media_publication_date_date'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            cur.execute("""
                CREATE INDEX media_publication_date_date
                ON media ((DATE(publication_date)))
            """)

        cnx.commit()
    finally:
        cur.close()
