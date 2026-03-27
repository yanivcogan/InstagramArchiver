"""
V002 — Add composite index on entity_share_link (entity, entity_id)
"""


def run(cnx):
    cur = cnx.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() "
            "  AND table_name = 'entity_share_link' "
            "  AND index_name = 'entity_share_link_entity_entity_id_index'",
        )
        if cur.fetchone()[0] > 0:
            print("    entity_share_link_entity_entity_id_index: already exists, skipping")
        else:
            print("    entity_share_link_entity_entity_id_index: creating ...", flush=True)
            cur.execute(
                "CREATE INDEX entity_share_link_entity_entity_id_index "
                "ON entity_share_link (entity, entity_id)"
            )
            print("    entity_share_link_entity_entity_id_index: created")
        cnx.commit()
    finally:
        cur.close()
