"""
V019 — Add optional password protection to entity_share_link

Adds password_hash and password_alg columns (both nullable) so individual
share links can require a password before granting access.
NULL in password_hash means no password (open access), matching existing behaviour.
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
        if not _column_exists(cur, "entity_share_link", "password_hash"):
            clauses.append("ADD COLUMN password_hash VARCHAR(255) NULL")
        if not _column_exists(cur, "entity_share_link", "password_alg"):
            clauses.append("ADD COLUMN password_alg VARCHAR(20) NULL")

        if not clauses:
            print("    entity_share_link: password columns already exist, skipping")
            return

        cur.execute("ALTER TABLE entity_share_link " + ", ".join(clauses))
        print(f"    entity_share_link: added password columns ({', '.join(clauses)})")
        cnx.commit()
    finally:
        cur.close()
