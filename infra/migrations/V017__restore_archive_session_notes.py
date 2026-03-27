"""
V017 — Restore notes column on archive_session

The notes column was incorrectly removed from archive_session in V015.
This migration adds it back and rebuilds the FULLTEXT index to include it.
"""

import time


def _column_exists(cur, table, column):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
        (table, column),
    )
    return cur.fetchone()[0] > 0


def _index_exists(cur, table, index_name):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s",
        (table, index_name),
    )
    return cur.fetchone()[0] > 0


def run(cnx):
    cur = cnx.cursor()
    try:
        notes_exists = _column_exists(cur, "archive_session", "notes")
        index_exists = _index_exists(cur, "archive_session", "idx_search_fulltext")

        if notes_exists and index_exists:
            # Check if the index already covers notes
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = 'archive_session' "
                "AND index_name = 'idx_search_fulltext' AND column_name = 'notes'",
            )
            if cur.fetchone()[0] > 0:
                print("    archive_session: notes column and fulltext index already correct, skipping")
                return

        clauses = []
        if index_exists:
            clauses.append("DROP INDEX idx_search_fulltext")
        if not notes_exists:
            clauses.append("ADD COLUMN notes text NULL")
        clauses.append("ADD FULLTEXT INDEX idx_search_fulltext (archived_url, archived_url_parts, notes)")

        t = time.perf_counter()
        cur.execute("ALTER TABLE archive_session " + ", ".join(clauses))
        print(f"    archive_session: restored notes column and rebuilt fulltext index ({time.perf_counter() - t:.1f}s)")

        cnx.commit()
    finally:
        cur.close()
