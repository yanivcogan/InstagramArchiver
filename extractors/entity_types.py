from datetime import datetime

from pydantic import BaseModel, Field
from typing import Optional, Any, Literal

class Account(BaseModel):
    url: str = Field(..., max_length=200)
    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=200)
    data: Optional[Any] = None
    notes: Optional[list[str]] = []
    sheet_entries: Optional[list[str]] = []

class Post(BaseModel):
    url: str = Field(..., max_length=250)
    account_url: Optional[str] = Field(None, max_length=200)
    publication_date: Optional[datetime] = None
    caption: Optional[str] = None
    data: Optional[Any] = None
    notes: Optional[list[str]] = []
    sheet_entries: Optional[list[str]] = []

t_media_type = Literal['video', 'audio', 'image']

class Media(BaseModel):
    url: str = Field(..., max_length=250)
    post_url: Optional[str] = Field(None, max_length=250)
    local_url: Optional[str] = None
    media_type: t_media_type
    data: Optional[Any] = None
    sheet_entries: Optional[list[str]] = []

class ExtractedSinglePost(BaseModel):
    post: Post
    media: list[Media] = Field(default_factory=list)

class ExtractedEntities(BaseModel):
    accounts: list[Account] = Field(default_factory=list)
    posts: list[ExtractedSinglePost] = Field(default_factory=list)

class ExtractedEntitiesFlattened(BaseModel):
    accounts: list[Account] = Field(default_factory=list)
    posts: list[Post] = Field(default_factory=list)
    media: list[Media] = Field(default_factory=list)