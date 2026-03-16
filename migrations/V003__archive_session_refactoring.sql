-- =============================================================================
-- archive_session table refactoring
-- =============================================================================
--
-- PURPOSE
-- -------
-- 1. Replaces the implicit state tracking spread across parsed_content,
--    extracted_entities, and extraction_error with a single explicit
--    incorporation_status ENUM column that is cheap to index and query.
--
-- 2. Renames parsed_content → parse_algorithm_version and
--    extracted_entities → extract_algorithm_version to reflect what they
--    actually store (algorithm version numbers, not boolean flags).
--
-- 3. Converts source_type from a magic integer to a self-documenting ENUM.
--
-- STATE MACHINE (linear — extraction always follows successful parsing)
-- -----------------------------------------------------------------------
--   pending       → archive registered, not yet parsed
--   parse_failed  → Part B failed; clear with clear_errors to retry
--   parsed        → Part B done, ready for Part C
--   extract_failed → Part C failed; clear with clear_errors to retry
--   done          → fully incorporated (Parts B + C complete)
--
-- BEFORE running this script:
--   1. Take a full database backup.
--   2. Ensure no incorporation job is running.
--   3. Requires MySQL 8.0+ for RENAME COLUMN and DROP INDEX IF EXISTS.
--
-- AFTER running this script, update the Python code:
--   - source_type = 1               → source_type = 'local_har'
--   - parsed_content                → parse_algorithm_version
--   - extracted_entities            → extract_algorithm_version
--   - parsed_content IS NULL ...    → incorporation_status = 'pending'
--   - parsed_content IS NOT NULL    → incorporation_status IN ('parsed','extract_failed','done')
--   - extracted_entities IS NULL    → incorporation_status != 'done'
--   - extraction_error IS NULL      → incorporation_status NOT IN ('parse_failed','extract_failed')
--   - Part B queue query            → WHERE incorporation_status = 'pending'
--   - Part C queue query            → WHERE incorporation_status = 'parsed'
--   - clear_errors (parse)          → SET incorporation_status = 'pending'   WHERE incorporation_status = 'parse_failed'
--   - clear_errors (extract)        → SET incorporation_status = 'parsed'    WHERE incorporation_status = 'extract_failed'
--
-- DDL statements cannot be rolled back in InnoDB.
-- Restore from backup if anything fails mid-script.
-- =============================================================================


-- =============================================================================
-- SECTION 1 — Add incorporation_status (nullable first so existing rows are valid)
-- =============================================================================

ALTER TABLE archive_session
    ADD COLUMN incorporation_status ENUM(
        'pending',
        'parse_failed',
        'parsed',
        'extract_failed',
        'done'
    ) NULL AFTER source_type;


-- =============================================================================
-- SECTION 2 — Migrate state from old implicit columns to the new single column
--
-- Old state encoding:
--   parsed_content IS NULL  + extraction_error IS NULL          → pending
--   parsed_content IS NULL  + extraction_error IS NOT NULL      → parse_failed
--   parsed_content IS NOT NULL + extracted_entities IS NULL
--       + extraction_error IS NULL                              → parsed
--   parsed_content IS NOT NULL + extraction_error IS NOT NULL   → extract_failed
--   parsed_content IS NOT NULL + extracted_entities IS NOT NULL
--       + extraction_error IS NULL                              → done
-- =============================================================================

UPDATE archive_session
SET incorporation_status = 'pending'
WHERE parsed_content IS NULL AND extraction_error IS NULL;

UPDATE archive_session
SET incorporation_status = 'parse_failed'
WHERE parsed_content IS NULL AND extraction_error IS NOT NULL;

UPDATE archive_session
SET incorporation_status = 'parsed'
WHERE parsed_content IS NOT NULL
  AND extracted_entities IS NULL
  AND extraction_error IS NULL;

UPDATE archive_session
SET incorporation_status = 'extract_failed'
WHERE parsed_content IS NOT NULL
  AND extraction_error IS NOT NULL;

UPDATE archive_session
SET incorporation_status = 'done'
WHERE parsed_content IS NOT NULL
  AND extracted_entities IS NOT NULL
  AND extraction_error IS NULL;


-- =============================================================================
-- SECTION 3 — Make incorporation_status NOT NULL now that all rows are populated
-- =============================================================================

ALTER TABLE archive_session
    MODIFY COLUMN incorporation_status ENUM(
        'pending',
        'parse_failed',
        'parsed',
        'extract_failed',
        'done'
    ) NOT NULL DEFAULT 'pending';


-- =============================================================================
-- SECTION 4 — Rename data columns to reflect what they actually store
-- =============================================================================

ALTER TABLE archive_session
    RENAME COLUMN parsed_content     TO parse_algorithm_version,
    RENAME COLUMN extracted_entities TO extract_algorithm_version;


-- =============================================================================
-- SECTION 5 — Convert source_type from magic integer to self-documenting ENUM
-- =============================================================================

ALTER TABLE archive_session
    ADD COLUMN source_type_new ENUM('AA_xlsx', 'local_har', 'local_wacz') NULL AFTER source_type;

UPDATE archive_session
SET source_type_new = CASE source_type
    WHEN 0 THEN 'AA_xlsx'
    WHEN 1 THEN 'local_har'
    WHEN 2 THEN 'local_wacz'
    ELSE NULL
END WHERE TRUE;

ALTER TABLE archive_session
    MODIFY COLUMN source_type_new ENUM('AA_xlsx', 'local_har', 'local_wacz') NOT NULL;

ALTER TABLE archive_session
    DROP COLUMN source_type;

ALTER TABLE archive_session
    RENAME COLUMN source_type_new TO source_type;


-- =============================================================================
-- SECTION 7 — Create the new composite index
--
-- Covers both pipeline queue queries with a two-column prefix:
--   Part B:  WHERE source_type = 'local_har' AND incorporation_status = 'pending'
--   Part C:  WHERE source_type = 'local_har' AND incorporation_status = 'parsed'
-- =============================================================================

CREATE INDEX idx_incorporation_queue
    ON archive_session (source_type, incorporation_status);


-- =============================================================================
-- SECTION 8 — Verification queries (uncomment and run manually to confirm)
-- =============================================================================

-- Row counts by new status (verify totals match pre-migration counts)
-- SELECT source_type, incorporation_status, COUNT(*) AS cnt
-- FROM archive_session
-- GROUP BY source_type, incorporation_status
-- ORDER BY source_type, incorporation_status;

-- Confirm no rows were left without a status
-- SELECT COUNT(*) AS unset_rows FROM archive_session WHERE incorporation_status IS NULL;

-- Confirm the index is used for the Part B queue query
-- EXPLAIN SELECT id, external_id, archive_location
-- FROM archive_session
-- WHERE source_type = 'local_har' AND incorporation_status = 'pending';

-- Confirm the index is used for the Part C queue query
-- EXPLAIN SELECT id, external_id, archive_location
-- FROM archive_session
-- WHERE source_type = 'local_har' AND incorporation_status = 'parsed';
