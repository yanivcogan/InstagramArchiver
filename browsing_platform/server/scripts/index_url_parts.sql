-- 1. Drop the idx_search_fulltext index
DROP INDEX idx_search_fulltext ON account;

-- 2. Update url_parts by splitting url on /, \, ?, ., & and joining with spaces
UPDATE account
SET url_parts = TRIM(
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(url, '/', ' '),
                '\\', ' '),
            '?', ' '),
        '.', ' '),
    '&', ' ')
) WHERE url_parts IS NULL;

-- 3. Recreate a FULLTEXT index over the specified columns
CREATE FULLTEXT INDEX idx_search_fulltext
ON account (url, url_parts, display_name, bio, notes);


-- 1. Drop the idx_search_fulltext index
DROP INDEX idx_search_fulltext ON archive_session;

-- 2. Update url_parts by splitting url on /, \, ?, ., & and joining with spaces
UPDATE archive_session
SET archived_url_parts = TRIM(
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(archived_url, '/', ' '),
                '\\', ' '),
            '?', ' '),
        '.', ' '),
    '&', ' ')
) WHERE archived_url IS NOT NULL AND archived_url_parts IS NULL;

-- 3. Recreate a FULLTEXT index over the specified columns
CREATE FULLTEXT INDEX idx_search_fulltext
ON archive_session (archived_url, archived_url_parts, notes);