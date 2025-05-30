from pydantic import BaseModel
from typing import List, Optional, Literal


class Comment(BaseModel):
    username: str
    user_id: Optional[str]
    text: str
    timestamp: Optional[int]

class Post(BaseModel):
    username: str
    user_id: str
    post_id: str
    caption: Optional[str]
    media_urls: List[str]
    timestamp: Optional[int]
    comments: List[Comment]
    mentions: List[str]
    type: Literal["post", "story", "reel", "highlight"] = "post"

