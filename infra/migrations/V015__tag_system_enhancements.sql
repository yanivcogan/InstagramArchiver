-- Migration 001: Tag System Enhancements
-- Run against an existing evidenceplatform database.

USE evidenceplatform;

-- 1.1 Drop temporal_constraint from tag_hierarchy
ALTER TABLE tag_hierarchy DROP COLUMN temporal_constraint;

-- 1.2 Drop notes from canonical entity tables and rebuild fulltext indexes

-- account
ALTER TABLE account DROP COLUMN notes;
ALTER TABLE account DROP INDEX idx_search_fulltext;
ALTER TABLE account ADD FULLTEXT INDEX idx_search_fulltext (url, url_parts, display_name, bio);

-- post
ALTER TABLE post DROP COLUMN notes;
ALTER TABLE post DROP INDEX idx_search_fulltext;
ALTER TABLE post ADD FULLTEXT INDEX idx_search_fulltext (caption, url);

-- media
ALTER TABLE media DROP COLUMN notes;
ALTER TABLE media DROP INDEX search_idx_fulltext;
ALTER TABLE media ADD FULLTEXT INDEX search_idx_fulltext (annotation);

-- media_part
ALTER TABLE media_part DROP COLUMN notes;

-- archive_session
ALTER TABLE archive_session DROP COLUMN notes;
ALTER TABLE archive_session DROP INDEX idx_search_fulltext;
ALTER TABLE archive_session ADD FULLTEXT INDEX idx_search_fulltext (archived_url, archived_url_parts);

-- 1.4 Add entity_affinity JSON column to tag_type (must run before 1.3 seed)
ALTER TABLE tag_type
    ADD COLUMN entity_affinity JSON NULL
    COMMENT 'e.g. ["account","post"] — which entity types this type is most used for. NULL = unrestricted.';

-- 1.3 Seed metadata tag type and notes tag
INSERT INTO tag_type (name, description, entity_affinity)
VALUES ('metadata', 'General-purpose curator metadata', '["account","post","media","media_part"]');

SET @meta_type_id = LAST_INSERT_ID();

INSERT INTO tag (name, description, tag_type_id)
VALUES ('notes', 'Free-form curator notes about this entity', @meta_type_id);

-- 1.5 Performance indexes on junction tables (tag_id direction)
CREATE INDEX idx_account_tag_tag_id    ON account_tag    (tag_id);
CREATE INDEX idx_post_tag_tag_id       ON post_tag       (tag_id);
CREATE INDEX idx_media_tag_tag_id      ON media_tag      (tag_id);
CREATE INDEX idx_media_part_tag_tag_id ON media_part_tag (tag_id);

-- tag_hierarchy sub_tag_id index for upward traversal
CREATE INDEX idx_tag_hierarchy_sub_tag_id ON tag_hierarchy (sub_tag_id);
