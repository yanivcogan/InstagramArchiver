"""
V024 — Add TOTP 2FA and pre-auth token support

Changes to `user` table:
  - totp_configured   TINYINT(1)   — has the user completed 2FA setup?
  - totp_secret       VARCHAR(64)  — active base32 TOTP secret
  - totp_method       VARCHAR(20)  — method type ('totp'); extensible for future WebAuthn etc.
  - totp_pending_secret VARCHAR(64) — secret stored during setup, cleared after confirmation
  - totp_last_used_at DATETIME     — last verified code timestamp (replay prevention)

New table `pre_auth_token`:
  Issued after successful password verification; consumed by subsequent login steps
  (TOTP verify, forced password change, forced TOTP setup). Single-use, 5-min TTL.

New table `totp_backup_code`:
  8 one-time-use Argon2id-hashed backup codes per user; used when authenticator is unavailable.
"""


def _column_exists(cur, table, column):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
        (table, column),
    )
    return cur.fetchone()[0] > 0


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
        # --- user table additions ---
        new_columns = [
            ("totp_configured",    "TINYINT(1) NOT NULL DEFAULT 0"),
            ("totp_secret",        "VARCHAR(64) NULL"),
            ("totp_method",        "VARCHAR(20) NULL DEFAULT 'totp'"),
            ("totp_pending_secret","VARCHAR(64) NULL"),
            ("totp_last_used_at",  "DATETIME NULL"),
        ]
        for col_name, col_def in new_columns:
            if _column_exists(cur, "user", col_name):
                print(f"    user.{col_name}: already exists, skipping")
            else:
                cur.execute(f"ALTER TABLE user ADD COLUMN {col_name} {col_def}")
                print(f"    user.{col_name}: added")

        # --- pre_auth_token table ---
        if _table_exists(cur, "pre_auth_token"):
            print("    pre_auth_token: already exists, skipping")
        else:
            cur.execute("""
                CREATE TABLE pre_auth_token (
                    id          INT AUTO_INCREMENT PRIMARY KEY,
                    user_id     INT NOT NULL,
                    token       VARCHAR(64) NOT NULL,
                    create_date DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    expires_at  DATETIME NOT NULL,
                    UNIQUE KEY uq_pre_auth_token (token),
                    CONSTRAINT fk_pre_auth_user
                        FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
                ) ENGINE=InnoDB
            """)
            print("    pre_auth_token: created")

        # --- totp_backup_code table ---
        if _table_exists(cur, "totp_backup_code"):
            print("    totp_backup_code: already exists, skipping")
        else:
            cur.execute("""
                CREATE TABLE totp_backup_code (
                    id        INT AUTO_INCREMENT PRIMARY KEY,
                    user_id   INT NOT NULL,
                    code_hash VARCHAR(255) NOT NULL,
                    used      TINYINT(1) NOT NULL DEFAULT 0,
                    CONSTRAINT fk_backup_user
                        FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
                ) ENGINE=InnoDB
            """)
            print("    totp_backup_code: created")

        cnx.commit()
    finally:
        cur.close()
