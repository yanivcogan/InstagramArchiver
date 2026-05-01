"""
V025 — Drop totp_backup_code table

Backup codes were removed from the 2FA mechanism. Account recovery is handled
entirely by the admin resetting a user's 2FA via the admin UI or the
disable_2fa.py script.
"""


def _table_exists(cur, table):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = %s",
        (table,),
    )
    return cur.fetchone()[0] > 0


def run(cnx):
    cur = cnx.cursor()
    try:
        if _table_exists(cur, "totp_backup_code"):
            cur.execute("DROP TABLE totp_backup_code")
            print("    totp_backup_code: dropped")
        else:
            print("    totp_backup_code: does not exist, skipping")
        cnx.commit()
    finally:
        cur.close()
