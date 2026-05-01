"""
V030 — Add aspect_ratio column to media table

Adds a DECIMAL(8,4) nullable column to store width/height ratio of each media asset.
The backfill reads each existing thumbnail (small JPEG, faster than the original file)
with PIL to measure its dimensions, then writes the calculated ratio in batches of 50
using a single CASE/WHEN UPDATE per batch to minimise DB round-trips.
"""

import os

from PIL import Image

from db_loaders.thumbnail_generator import LOCAL_THUMBNAILS_DIR_ALIAS, ROOT_THUMBNAILS

BATCH_SIZE = 50


def run(cnx):
    cur = cnx.cursor(dictionary=True)
    try:
        # ------------------------------------------------------------------ #
        # Step 1: Add the column
        # ------------------------------------------------------------------ #
        cur.execute(
            """SELECT COUNT(*) AS cnt
               FROM information_schema.columns
               WHERE table_schema = DATABASE()
                 AND table_name = 'media'
                 AND column_name = 'aspect_ratio'"""
        )
        if cur.fetchone()['cnt'] > 0:
            print("    V030: aspect_ratio column already exists, skipping ALTER")
        else:
            cur.execute(
                """ALTER TABLE media
                   ADD COLUMN aspect_ratio DECIMAL(8,4) NULL AFTER thumbnail_path"""
            )
            cnx.commit()
            print("    V030: aspect_ratio column added")

        # ------------------------------------------------------------------ #
        # Step 2: Backfill from existing thumbnails
        # ------------------------------------------------------------------ #
        # Advance via id > last_id so every batch makes progress even when all
        # thumbnail files in a batch are missing from disk.
        total_updated = 0
        last_id = 0
        while True:
            cur.execute(
                """SELECT id, thumbnail_path FROM media
                   WHERE id > %s
                     AND thumbnail_path IS NOT NULL
                     AND thumbnail_path NOT LIKE 'error:%%'
                     AND aspect_ratio IS NULL
                   ORDER BY id
                   LIMIT %s""",
                (last_id, BATCH_SIZE),
            )
            rows = cur.fetchall()
            if not rows:
                break

            last_id = rows[-1]['id']

            updates = {}
            for row in rows:
                # thumbnail_path is stored as 'local_thumbnails/{hash}.jpg'
                filename = row['thumbnail_path'].replace(LOCAL_THUMBNAILS_DIR_ALIAS + '/', '', 1)
                full_path = os.path.join(str(ROOT_THUMBNAILS), filename)
                if not os.path.exists(full_path):
                    continue
                try:
                    with Image.open(full_path) as img:
                        if img.height > 0:
                            updates[row['id']] = img.width / img.height
                except Exception:
                    continue

            if not updates:
                continue

            ids = list(updates.keys())
            cases = ' '.join('WHEN %s THEN %s' for _ in ids)
            in_clause = ','.join(['%s'] * len(ids))
            values = [v for media_id in ids for v in (media_id, updates[media_id])]
            cur.execute(
                f"UPDATE media SET aspect_ratio = CASE id {cases} END WHERE id IN ({in_clause})",
                values + ids,
            )
            cnx.commit()
            total_updated += len(ids)

        print(f"    V030: backfilled aspect_ratio for {total_updated} media row(s)")
        print("    V030: done")
    finally:
        cur.close()
