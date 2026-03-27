"""
V003 — archive_session table refactoring

Optimisations applied vs the original SQL:
  - FULLTEXT index dropped first and recreated last so ALTER TABLE steps are not
    blocked by the FULLTEXT constraint and MySQL can use INPLACE where possible.
  - 5 separate UPDATEs collapsed into 1 CASE UPDATE (one table scan).
  - incorporation_status added as NOT NULL DEFAULT 'pending' so the follow-up
    MODIFY to make it NOT NULL is unnecessary.
  - Step 6 split into two ALTER TABLE statements to avoid a MySQL restriction:
    you cannot DROP a column and RENAME another column to the same name in one
    statement.

Every step is idempotent — the migration can be re-run after a partial failure
without restoring from backup.
"""

import time


class _Timer:
    def __init__(self, label: str):
        self._label = label

    def __enter__(self):
        print(f"    [{self._label}] starting ...", flush=True)
        self._t = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.perf_counter() - self._t
        if exc_type is None:
            print(f"    [{self._label}] done in {elapsed:.1f}s", flush=True)
        else:
            print(f"    [{self._label}] FAILED after {elapsed:.1f}s", flush=True)
        return False  # never suppress exceptions


def _col_exists(cur, column):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.columns"
        " WHERE table_schema = DATABASE()"
        " AND table_name = 'archive_session' AND column_name = %s",
        (column,),
    )
    return cur.fetchone()[0] > 0


def _idx_exists(cur, index):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.statistics"
        " WHERE table_schema = DATABASE()"
        " AND table_name = 'archive_session' AND index_name = %s",
        (index,),
    )
    return cur.fetchone()[0] > 0


def run(cnx):
    cur = cnx.cursor()
    try:
        # ------------------------------------------------------------------
        # STEP 0 — Drop the FULLTEXT index so ALTER TABLE steps can use
        # INPLACE.  Guarded for safe retry.
        # ------------------------------------------------------------------
        if _idx_exists(cur, "idx_search_fulltext"):
            with _Timer("Step 0 — drop FULLTEXT index (recreated at end)"):
                cur.execute("DROP INDEX idx_search_fulltext ON archive_session")
        else:
            print("    [Step 0] FULLTEXT index already absent, skipping", flush=True)

        # ------------------------------------------------------------------
        # STEP 1 — Add incorporation_status as NOT NULL DEFAULT 'pending'.
        # ------------------------------------------------------------------
        if not _col_exists(cur, "incorporation_status"):
            with _Timer("Step 1 — add incorporation_status"):
                cur.execute("""
                    ALTER TABLE archive_session
                        ADD COLUMN incorporation_status ENUM(
                            'pending',
                            'parse_failed',
                            'parsed',
                            'extract_failed',
                            'done'
                        ) NOT NULL DEFAULT 'pending' AFTER source_type
                """)
        else:
            print("    [Step 1] incorporation_status already exists, skipping", flush=True)

        # ------------------------------------------------------------------
        # STEP 2 — Populate incorporation_status in one pass.
        #
        # References parsed_content / extracted_entities (old column names).
        # Only meaningful before Step 3 renames them; skip if already renamed.
        # ------------------------------------------------------------------
        if _col_exists(cur, "parsed_content"):
            with _Timer("Step 2 — populate incorporation_status (single table scan)"):
                cur.execute("""
                    UPDATE archive_session
                    SET incorporation_status = CASE
                        WHEN parsed_content IS NULL     AND extraction_error IS NOT NULL THEN 'parse_failed'
                        WHEN parsed_content IS NOT NULL AND extracted_entities IS NULL
                             AND extraction_error IS NULL                               THEN 'parsed'
                        WHEN parsed_content IS NOT NULL AND extraction_error IS NOT NULL THEN 'extract_failed'
                        WHEN parsed_content IS NOT NULL AND extracted_entities IS NOT NULL
                             AND extraction_error IS NULL                               THEN 'done'
                        ELSE 'pending'
                    END
                """)
                print(f"      ({cur.rowcount} rows updated)", flush=True)
        else:
            print("    [Step 2] parsed_content already renamed, skipping backfill", flush=True)

        # ------------------------------------------------------------------
        # STEP 3 — Rename data columns (metadata-only).
        # ------------------------------------------------------------------
        if _col_exists(cur, "parsed_content"):
            with _Timer("Step 3 — rename parsed_content / extracted_entities"):
                cur.execute("""
                    ALTER TABLE archive_session
                        RENAME COLUMN parsed_content     TO parse_algorithm_version,
                        RENAME COLUMN extracted_entities TO extract_algorithm_version
                """)
        else:
            print("    [Step 3] columns already renamed, skipping", flush=True)

        # ------------------------------------------------------------------
        # STEP 4 — Add source_type_new.
        # ------------------------------------------------------------------
        if not _col_exists(cur, "source_type_new"):
            with _Timer("Step 4 — add source_type_new column"):
                cur.execute("""
                    ALTER TABLE archive_session
                        ADD COLUMN source_type_new ENUM('AA_xlsx', 'local_har', 'local_wacz') NULL AFTER source_type
                """)
        else:
            print("    [Step 4] source_type_new already exists, skipping", flush=True)

        # ------------------------------------------------------------------
        # STEP 5 — Populate source_type_new (only if it exists, i.e. the
        # rename in Step 6b hasn't happened yet).
        # ------------------------------------------------------------------
        if _col_exists(cur, "source_type_new"):
            with _Timer("Step 5 — populate source_type_new"):
                cur.execute("""
                    UPDATE archive_session
                    SET source_type_new = CASE source_type
                        WHEN 0 THEN 'AA_xlsx'
                        WHEN 1 THEN 'local_har'
                        WHEN 2 THEN 'local_wacz'
                        ELSE NULL
                    END
                """)
                print(f"      ({cur.rowcount} rows updated)", flush=True)
        else:
            print("    [Step 5] source_type_new absent (already renamed), skipping", flush=True)

        # ------------------------------------------------------------------
        # STEP 6a — Make source_type_new NOT NULL and drop the old integer
        # source_type column.
        #
        # Split from Step 6b because MySQL does not allow dropping a column
        # and renaming another column to the same name in one statement.
        # ------------------------------------------------------------------
        if _col_exists(cur, "source_type_new"):
            with _Timer("Step 6a — make source_type_new NOT NULL + drop old source_type"):
                cur.execute("""
                    ALTER TABLE archive_session
                        MODIFY COLUMN source_type_new ENUM('AA_xlsx', 'local_har', 'local_wacz') NOT NULL,
                        DROP COLUMN source_type
                """)

            # ------------------------------------------------------------------
            # STEP 6b — Rename source_type_new → source_type.
            # ------------------------------------------------------------------
            with _Timer("Step 6b — rename source_type_new to source_type"):
                cur.execute("""
                    ALTER TABLE archive_session
                        RENAME COLUMN source_type_new TO source_type
                """)
        else:
            print("    [Step 6] source_type conversion already done, skipping", flush=True)

        # ------------------------------------------------------------------
        # STEP 7 — Create composite index.
        # ------------------------------------------------------------------
        if not _idx_exists(cur, "idx_incorporation_queue"):
            with _Timer("Step 7 — create idx_incorporation_queue index"):
                cur.execute("""
                    CREATE INDEX idx_incorporation_queue
                        ON archive_session (source_type, incorporation_status)
                """)
        else:
            print("    [Step 7] idx_incorporation_queue already exists, skipping", flush=True)

        # ------------------------------------------------------------------
        # STEP 8 — Recreate the FULLTEXT index dropped in Step 0.
        # ------------------------------------------------------------------
        if not _idx_exists(cur, "idx_search_fulltext"):
            with _Timer("Step 8 — recreate idx_search_fulltext (FULLTEXT)"):
                cur.execute("""
                    CREATE FULLTEXT INDEX idx_search_fulltext
                        ON archive_session (archived_url, archived_url_parts, notes)
                """)
        else:
            print("    [Step 8] FULLTEXT index already present, skipping", flush=True)

    finally:
        cur.close()
