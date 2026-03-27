"""
V016 — Add quick_access column to tag
"""


def run(cnx):
    cur = cnx.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() "
            "  AND table_name = 'tag' AND column_name = 'quick_access'",
        )
        if cur.fetchone()[0] > 0:
            print("    tag.quick_access: already exists, skipping")
        else:
            print("    tag.quick_access: adding ...", flush=True)
            cur.execute(
                "ALTER TABLE tag ADD COLUMN quick_access TINYINT(1) NOT NULL DEFAULT 0"
            )
            print("    tag.quick_access: added")
        cnx.commit()
    finally:
        cur.close()
