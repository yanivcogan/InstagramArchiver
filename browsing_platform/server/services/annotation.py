from pydantic import BaseModel
from typing import List, Optional


class Annotation(BaseModel):
    notes: Optional[str] = None
    tags: Optional[List[int]] = None