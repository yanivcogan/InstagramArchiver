import json
from typing import List, Optional

from pydantic import BaseModel

from browsing_platform.server.services.tag import ENTITY_TAG_TABLES
from utils import db


def validate_tags_entity_affinity(tag_ids: list[int], entity_type: str) -> list[int]:
    """Returns IDs of tags whose type has entity_affinity set that excludes entity_type."""
    if not tag_ids:
        return []
    in_clause = ', '.join([f"%(id_{i})s" for i in range(len(tag_ids))])
    args: dict = {f"id_{i}": tag_id for i, tag_id in enumerate(tag_ids)}
    args["entity_json"] = json.dumps(entity_type)
    rows = db.execute_query(
        f"""SELECT t.id FROM tag t
           JOIN tag_type tt ON t.tag_type_id = tt.id
           WHERE t.id IN ({in_clause})
             AND tt.entity_affinity IS NOT NULL
             AND NOT JSON_CONTAINS(tt.entity_affinity, %(entity_json)s)""",
        args,
        return_type="rows"
    )
    return [row["id"] for row in rows]


class TagWithNotes(BaseModel):
    id: int
    notes: Optional[str] = None


class Annotation(BaseModel):
    tags: Optional[List[TagWithNotes]] = None


def add_tags_batch(entity_type: str, entity_ids: list[int], tags: list[TagWithNotes]) -> None:
    if entity_type not in ENTITY_TAG_TABLES:
        raise ValueError(f"Unsupported entity type: {entity_type}")
    table_name, id_col = ENTITY_TAG_TABLES[entity_type]
    for entity_id in entity_ids:
        for tag in tags:
            db.execute_query(
                f"INSERT IGNORE INTO {table_name} ({id_col}, tag_id, notes) "
                "VALUES (%(eid)s, %(tid)s, %(notes)s)",
                {"eid": entity_id, "tid": tag.id, "notes": tag.notes},
                return_type="none"
            )
