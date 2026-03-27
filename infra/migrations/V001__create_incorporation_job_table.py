"""
V001 — Create incorporation_job table
"""


def _table_exists(cur, table_name):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = %s",
        (table_name,),
    )
    return cur.fetchone()[0] > 0


def run(cnx):
    cur = cnx.cursor()
    try:
        if _table_exists(cur, "incorporation_job"):
            print("    incorporation_job: already exists, skipping")
        else:
            print("    incorporation_job: creating ...", flush=True)
            cur.execute("""
                CREATE TABLE incorporation_job (
                    id            INT AUTO_INCREMENT PRIMARY KEY,
                    started_at    DATETIME NOT NULL,
                    completed_at  DATETIME,
                    status        ENUM('running','completed','failed') NOT NULL DEFAULT 'running',
                    triggered_by_user_id INT,
                    triggered_by_ip      VARCHAR(255),
                    log           MEDIUMTEXT,
                    error         TEXT
                )
            """)
            print("    incorporation_job: created")
        cnx.commit()
    finally:
        cur.close()
