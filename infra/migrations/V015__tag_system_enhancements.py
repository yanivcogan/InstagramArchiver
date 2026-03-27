"""
V015 — Tag system enhancements

- Drop temporal_constraint column from tag_hierarchy
- Drop notes columns from account, post, media, media_part, archive_session
  and rebuild their FULLTEXT indexes without that column
- Add entity_affinity JSON column to tag_type
- Seed metadata tag type and notes tag
- Add performance indexes on junction tables (tag_id direction)
- Add sub_tag_id index on tag_hierarchy for upward traversal

Note: drop index, drop column, and add index are combined into a single ALTER TABLE
so MySQL performs one table rebuild instead of three.
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


def _drop_notes_and_rebuild_fulltext(cur, table, index_name, new_index_columns):
    """Drop notes column and rebuild FULLTEXT index in a single ALTER (one table rebuild)."""
    notes_exists = _column_exists(cur, table, "notes")
    index_exists = _index_exists(cur, table, index_name)

    if not notes_exists and index_exists:
        print(f"    {table}: already migrated, skipping")
        return

    clauses = []
    if index_exists:
        clauses.append(f"DROP INDEX {index_name}")
    if notes_exists:
        clauses.append("DROP COLUMN notes")
    if not index_exists or notes_exists:
        clauses.append(f"ADD FULLTEXT INDEX {index_name} ({new_index_columns})")

    t = time.perf_counter()
    cur.execute(f"ALTER TABLE {table} " + ", ".join(clauses))
    print(f"    {table}: migrated ({time.perf_counter() - t:.1f}s)")


def run(cnx):
    cur = cnx.cursor()
    try:
        # 1.1 Drop temporal_constraint from tag_hierarchy
        if _column_exists(cur, "tag_hierarchy", "temporal_constraint"):
            t = time.perf_counter()
            cur.execute("ALTER TABLE tag_hierarchy DROP COLUMN temporal_constraint")
            print(f"    tag_hierarchy: dropped temporal_constraint ({time.perf_counter() - t:.1f}s)")
        else:
            print("    tag_hierarchy: temporal_constraint already absent, skipping")

        # 1.2 Drop notes + rebuild FULLTEXT for each affected table
        _drop_notes_and_rebuild_fulltext(
            cur, "account", "idx_search_fulltext", "url, url_parts, display_name, bio"
        )
        _drop_notes_and_rebuild_fulltext(
            cur, "post", "idx_search_fulltext", "caption, url"
        )
        _drop_notes_and_rebuild_fulltext(
            cur, "media", "search_idx_fulltext", "annotation"
        )

        if _column_exists(cur, "media_part", "notes"):
            t = time.perf_counter()
            cur.execute("ALTER TABLE media_part DROP COLUMN notes")
            print(f"    media_part: dropped notes column ({time.perf_counter() - t:.1f}s)")
        else:
            print("    media_part: notes already absent, skipping")

        _drop_notes_and_rebuild_fulltext(
            cur, "archive_session", "idx_search_fulltext", "archived_url, archived_url_parts"
        )

        # 1.4 Add entity_affinity JSON column to tag_type
        if not _column_exists(cur, "tag_type", "entity_affinity"):
            t = time.perf_counter()
            cur.execute("""
                ALTER TABLE tag_type
                    ADD COLUMN entity_affinity JSON NULL
                    COMMENT 'e.g. ["account","post"] — which entity types this type is most used for. NULL = unrestricted.'
            """)
            print(f"    tag_type: added entity_affinity ({time.perf_counter() - t:.1f}s)")
        else:
            print("    tag_type: entity_affinity already exists, skipping")

        # 1.3 Seed metadata tag type
        cur.execute("SELECT id FROM tag_type WHERE name = 'metadata'")
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "INSERT INTO tag_type (name, description, entity_affinity) "
                "VALUES ('metadata', 'General-purpose curator metadata', "
                "'[\"account\",\"post\",\"media\",\"media_part\"]')"
            )
            meta_type_id = cur.lastrowid
            print("    tag_type: inserted metadata type")
        else:
            meta_type_id = row[0]
            print("    tag_type: metadata type already exists, skipping")

        # Seed notes tag
        cur.execute(
            "SELECT id FROM tag WHERE name = 'notes' AND tag_type_id = %s",
            (meta_type_id,),
        )
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO tag (name, description, tag_type_id) "
                "VALUES ('notes', 'Free-form curator notes about this entity', %s)",
                (meta_type_id,),
            )
            print("    tag: inserted notes tag")
        else:
            print("    tag: notes tag already exists, skipping")

        # 1.5 Performance indexes on junction tables (tag_id direction)
        for index_name, table in [
            ("idx_account_tag_tag_id",    "account_tag"),
            ("idx_post_tag_tag_id",       "post_tag"),
            ("idx_media_tag_tag_id",      "media_tag"),
            ("idx_media_part_tag_tag_id", "media_part_tag"),
        ]:
            if not _index_exists(cur, table, index_name):
                t = time.perf_counter()
                cur.execute(f"CREATE INDEX {index_name} ON {table} (tag_id)")
                print(f"    {index_name}: created ({time.perf_counter() - t:.1f}s)")
            else:
                print(f"    {index_name}: already exists, skipping")

        if not _index_exists(cur, "tag_hierarchy", "idx_tag_hierarchy_sub_tag_id"):
            t = time.perf_counter()
            cur.execute("CREATE INDEX idx_tag_hierarchy_sub_tag_id ON tag_hierarchy (sub_tag_id)")
            print(f"    idx_tag_hierarchy_sub_tag_id: created ({time.perf_counter() - t:.1f}s)")
        else:
            print("    idx_tag_hierarchy_sub_tag_id: already exists, skipping")

        cnx.commit()
    finally:
        cur.close()
