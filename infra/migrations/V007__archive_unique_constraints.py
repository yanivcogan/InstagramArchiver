"""
Add UNIQUE(canonical_id, archive_session_id) to each *_archive table.

This enforces at the DB level the invariant that re-processing an archive
session can only UPDATE an existing archive record, never INSERT a duplicate.

Before adding each constraint the migration checks for existing duplicates
and aborts with a clear message if any are found, so the database is never
left in a broken state. Duplicate rows must be resolved manually before
re-running.

Also adds these constraints to the target create_db.sql schema (new
installations get them automatically).
"""

CONSTRAINTS = [
    (
        "account_archive",
        "uq_account_archive_canonical_session",
        "canonical_id, archive_session_id",
    ),
    (
        "post_archive",
        "uq_post_archive_canonical_session",
        "canonical_id, archive_session_id",
    ),
    (
        "media_archive",
        "uq_media_archive_canonical_session",
        "canonical_id, archive_session_id",
    ),
]


def _constraint_exists(cur, table: str, constraint_name: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM information_schema.table_constraints
        WHERE table_schema    = DATABASE()
          AND table_name      = %s
          AND constraint_name = %s
          AND constraint_type = 'UNIQUE'
        """,
        (table, constraint_name),
    )
    row = cur.fetchone()
    return (row["cnt"] if isinstance(row, dict) else row[0]) > 0


def _find_duplicates(cur, table: str) -> list[dict]:
    """Return rows where (canonical_id, archive_session_id) appears more than once."""
    cur.execute(
        f"""
        SELECT canonical_id, archive_session_id, COUNT(*) AS cnt
        FROM {table}
        WHERE canonical_id IS NOT NULL
        GROUP BY canonical_id, archive_session_id
        HAVING cnt > 1
        """
    )
    rows = cur.fetchall()
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return rows
    # tuple rows — convert to dicts using cursor description
    cols = [d[0] for d in cur.description]
    return [{cols[i]: row[i] for i in range(len(cols))} for row in rows]


def run(cnx):
    cur = cnx.cursor(dictionary=True)

    for table, constraint_name, columns in CONSTRAINTS:
        if _constraint_exists(cur, table, constraint_name):
            print(f"    {table}: constraint '{constraint_name}' already exists, skipping")
            continue

        duplicates = _find_duplicates(cur, table)
        if duplicates:
            lines = "\n".join(
                f"      canonical_id={r['canonical_id']}, "
                f"archive_session_id={r['archive_session_id']}, "
                f"count={r['cnt']}"
                for r in duplicates
            )
            raise RuntimeError(
                f"\n    Cannot add unique constraint to '{table}': {len(duplicates)} duplicate "
                f"(canonical_id, archive_session_id) group(s) found:\n{lines}\n"
                f"    Resolve duplicates manually before re-running this migration."
            )

        cur.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} UNIQUE ({columns})"
        )
        print(f"    {table}: added constraint '{constraint_name}'")

    cur.close()
