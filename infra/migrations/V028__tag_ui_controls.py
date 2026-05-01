"""
V028 — Add tag_type.quick_access, tag.omit_from_tag_type_dropdown, tag.notes_recommended
"""


def run(cnx):
    cur = cnx.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() "
            "  AND table_name = 'tag_type' AND column_name = 'quick_access'",
        )
        if cur.fetchone()[0] > 0:
            print("    tag_type.quick_access: already exists, skipping")
        else:
            print("    tag_type.quick_access: adding ...", flush=True)
            cur.execute(
                "ALTER TABLE tag_type ADD COLUMN quick_access TINYINT(1) NOT NULL DEFAULT 0"
            )
            print("    tag_type.quick_access: added")

        cur.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() "
            "  AND table_name = 'tag' AND column_name = 'omit_from_tag_type_dropdown'",
        )
        if cur.fetchone()[0] > 0:
            print("    tag.omit_from_tag_type_dropdown: already exists, skipping")
        else:
            print("    tag.omit_from_tag_type_dropdown: adding ...", flush=True)
            cur.execute(
                "ALTER TABLE tag ADD COLUMN omit_from_tag_type_dropdown TINYINT(1) NOT NULL DEFAULT 0"
            )
            print("    tag.omit_from_tag_type_dropdown: added")

        cur.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() "
            "  AND table_name = 'tag' AND column_name = 'notes_recommended'",
        )
        if cur.fetchone()[0] > 0:
            print("    tag.notes_recommended: already exists, skipping")
        else:
            print("    tag.notes_recommended: adding ...", flush=True)
            cur.execute(
                "ALTER TABLE tag ADD COLUMN notes_recommended TINYINT(1) NOT NULL DEFAULT 1"
            )
            print("    tag.notes_recommended: added")

        cnx.commit()
    finally:
        cur.close()
