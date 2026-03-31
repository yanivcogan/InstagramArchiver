from typing import List, Optional

from pydantic import BaseModel

from browsing_platform.server.services.tag import ENTITY_TAG_TABLES
from utils import db


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
