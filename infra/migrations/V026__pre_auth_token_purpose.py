"""
V026 — Add purpose column to pre_auth_token

Each pre_auth_token is now tagged with the login step it was issued for, so
endpoints can reject tokens issued for a different step (purpose binding).

Valid values: 'change_password', 'setup_totp', 'setup_totp_enable', 'verify_totp'

Any rows that exist at migration time are deleted because they were issued
without a purpose and are no longer valid (TTL is 5 minutes anyway).
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
        if not _column_exists(cur, "pre_auth_token", "purpose"):
            cur.execute(
                "ALTER TABLE pre_auth_token "
                "ADD COLUMN purpose VARCHAR(32) NOT NULL DEFAULT 'unknown'"
            )
            cur.execute("DELETE FROM pre_auth_token WHERE purpose = 'unknown'")
            print("    pre_auth_token.purpose: added, stale rows deleted")
        else:
            print("    pre_auth_token.purpose: already exists, skipping")
        cnx.commit()
    finally:
        cur.close()
