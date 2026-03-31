"""
V018 — Add attachment-access flags to entity_share_link

Adds include_screen_recordings and include_har columns so that share links
can be configured to withhold access to those file types from recipients.
Defaults to 1 (include) so existing links are unaffected.
"""


def _column_exists(cur, table, column):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
        (table, column),
    )
    return cur.fetchone()[0] > 0


def run(cnx):
    cur = cnx.cursor()
    try:
        clauses = []
        if not _column_exists(cur, "entity_share_link", "include_screen_recordings"):
            clauses.append("ADD COLUMN include_screen_recordings TINYINT NOT NULL DEFAULT 1")
        if not _column_exists(cur, "entity_share_link", "include_har"):
            clauses.append("ADD COLUMN include_har TINYINT NOT NULL DEFAULT 1")

        if not clauses:
            print("    entity_share_link: attachment-access columns already exist, skipping")
            return

        cur.execute("ALTER TABLE entity_share_link " + ", ".join(clauses))
        print(f"    entity_share_link: added attachment-access columns ({', '.join(clauses)})")
        cnx.commit()
    finally:
        cur.close()
