from datetime import datetime

from pydantic import BaseModel
from typing import Optional

import db


class ITag(BaseModel):
    id: Optional[int] = None
    create_date: Optional[datetime] = None
    update_date: Optional[datetime] = None
    name: str
    description: Optional[str] = None
    tag_type_id: Optional[int] = None

class ITagWithType(ITag):
    tag_type_name: Optional[str] = None
    tag_type_description: Optional[str] = None
    tag_type_notes: Optional[str] = None



def auto_complete_tags(query: str) -> list[ITagWithType]:
    matching_rows = db.execute_query(
        """SELECT 
                tag.*,
                tag_type.name AS tag_type_name,
                tag_type.description AS tag_type_description,
                tag_type.notes AS tag_type_notes
            FROM tag
            LEFT JOIN tag_type ON tag.tag_type_id = tag_type.id
            WHERE tag.name LIKE %(query)s
            LIMIT 10""",
        {"query": f"%{query}%"},
        return_type="rows"
    )
    return [ITagWithType(**row) for row in matching_rows]