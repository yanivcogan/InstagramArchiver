from typing import List, Optional

from pydantic import BaseModel


class TagWithNotes(BaseModel):
    id: int
    notes: Optional[str] = None


class Annotation(BaseModel):
    tags: Optional[List[TagWithNotes]] = None
