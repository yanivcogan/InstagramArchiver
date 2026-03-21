def run(cnx):
    cur = cnx.cursor()
    try:
        # Add thumbnail_status column if it doesn't exist
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'media'
              AND column_name = 'thumbnail_status'
        """)
        (count,) = cur.fetchone()
        if count == 0:
            cur.execute("""
                ALTER TABLE media
                ADD COLUMN thumbnail_status
                    ENUM('pending', 'generated', 'not_needed', 'error')
                    NOT NULL DEFAULT 'pending'
                    AFTER thumbnail_path
            """)

            # Backfill from existing data
            # Already has a valid thumbnail path → generated
            cur.execute("""
                UPDATE media
                SET thumbnail_status = 'generated'
                WHERE thumbnail_path IS NOT NULL
                  AND thumbnail_path NOT LIKE 'error:%'
            """)
            # Previously failed thumbnail generation → error
            cur.execute("""
                UPDATE media
                SET thumbnail_status = 'error'
                WHERE thumbnail_path LIKE 'error:%'
            """)
            # No local file, or audio → not_needed (can never generate a thumbnail)
            cur.execute("""
                UPDATE media
                SET thumbnail_status = 'not_needed'
                WHERE thumbnail_status = 'pending'
                  AND (local_url IS NULL OR media_type = 'audio')
            """)
            # Everything else with a local file keeps the default 'pending'

            # Index for fast pending-thumbnail lookups
            cur.execute("""
                CREATE INDEX media_thumbnail_status_index
                ON media (thumbnail_status)
            """)

        cnx.commit()
    finally:
        cur.close()
