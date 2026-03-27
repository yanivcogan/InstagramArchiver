-- Add composite index on entity_share_link to support the query:
-- WHERE entity = ? AND entity_id = ? (ORDER BY create_date DESC LIMIT 1)
-- The link_suffix unique constraint already covers WHERE link_suffix = ? lookups.
CREATE INDEX entity_share_link_entity_entity_id_index
    ON entity_share_link (entity, entity_id);