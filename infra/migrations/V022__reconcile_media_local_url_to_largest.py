"""
V022 — Reconcile canonical media.local_url to the largest available archive file

Before commit 1fc1440 the reconcile_media logic did not compare file sizes, so
media.local_url could end up pointing to a smaller/older archive copy even when
a larger version existed in another media_archive row.

This migration:
  1. Finds every media row that has 2+ media_archive entries with a non-null
     local_url (meaning multiple physical copies exist on disk)
  2. For each, picks the local_url pointing to the largest existing file
  3. Updates media.local_url if a better copy is available
  4. Resets thumbnail_status to 'pending' and clears thumbnail_path when the
     canonical file changes, so thumbnails regenerate from the new best copy
"""

from extractors.reconcile_entities import _local_url_size


BATCH_SIZE = 100


def run(cnx):
    cur = cnx.cursor()
    try:
        # ------------------------------------------------------------------ #
        # Step 1: Find media rows with multiple non-null archive copies
        # ------------------------------------------------------------------ #
        cur.execute(
            """SELECT m.id, m.local_url
               FROM media m
               WHERE (
                   SELECT COUNT(*)
                   FROM media_archive ma
                   WHERE ma.canonical_id = m.id
                     AND ma.local_url IS NOT NULL
               ) > 1"""
        )
        candidates = cur.fetchall()
        print(f"    V022: {len(candidates)} media row(s) have multiple archive copies")

        if not candidates:
            print("    V022: nothing to do")
            return

        # ------------------------------------------------------------------ #
        # Step 2: For each candidate, pick the largest archive copy
        # ------------------------------------------------------------------ #
        updated_count = 0
        batch_pending = 0

        for media_id, current_local_url in candidates:
            cur.execute(
                "SELECT local_url FROM media_archive WHERE canonical_id = %s AND local_url IS NOT NULL",
                (media_id,),
            )
            archive_urls = [row[0] for row in cur.fetchall()]

            best_url: str | None = None
            best_size: int = -1
            for url in archive_urls:
                size = _local_url_size(url)
                if size > best_size:
                    best_size = size
                    best_url = url

            if best_url is None or best_url == current_local_url:
                continue

            cur.execute(
                """UPDATE media
                   SET local_url = %s,
                       thumbnail_status = 'pending',
                       thumbnail_path = NULL
                   WHERE id = %s""",
                (best_url, media_id),
            )
            updated_count += 1
            batch_pending += 1

            if batch_pending >= BATCH_SIZE:
                cnx.commit()
                batch_pending = 0

        if batch_pending > 0:
            cnx.commit()

        print(f"    V022: updated {updated_count} media row(s)")
        print("    V022: done")

    finally:
        cur.close()
