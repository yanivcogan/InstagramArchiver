from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Literal
import json

class Account(BaseModel):
    url: str = Field(..., max_length=200)
    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=200)
    data: Optional[Any] = None
    notes: Optional[list[str]] = []
    sheet_entries: Optional[list[str]] = []

    @field_validator('url', mode='before')
    def normalize_url(cls, v, _):
        if isinstance(v, str):
            v = v.strip().rstrip('/')
        return v

    @field_validator('data', mode='before')
    def parse_data(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        return v

    @field_validator('notes', mode='before')
    def parse_notes(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = []
        elif v is None:
            v = []
        return v

    @field_validator('sheet_entries', mode='before')
    def parse_sheet_entries(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = []
        elif v is None:
            v = []
        return v

class Post(BaseModel):
    url: str = Field(..., max_length=250)
    account_url: Optional[str] = Field(None, max_length=200)
    publication_date: Optional[datetime] = None
    caption: Optional[str] = None
    data: Optional[Any] = None
    notes: Optional[list[str]] = []
    sheet_entries: Optional[list[str]] = []

    @field_validator('url', mode='before')
    def normalize_url(cls, v, _):
        if isinstance(v, str):
            v = v.strip().rstrip('/')
        return v

    @field_validator('account_url', mode='before')
    def normalize_account_url(cls, v, _):
        if isinstance(v, str):
            v = v.strip().rstrip('/')
        return v

    @field_validator('data', mode='before')
    def parse_data(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        return v

    @field_validator('notes', mode='before')
    def parse_notes(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = []
        elif v is None:
            v = []
        return v

    @field_validator('sheet_entries', mode='before')
    def parse_sheet_entries(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = []
        elif v is None:
            v = []
        return v

t_media_type = Literal['video', 'audio', 'image']

class Media(BaseModel):
    url: str = Field(..., max_length=250)
    post_url: Optional[str] = Field(None, max_length=250)
    local_url: Optional[str] = None
    media_type: t_media_type
    data: Optional[Any] = None
    sheet_entries: Optional[list[str]] = []

    @field_validator('url', mode='before')
    def normalize_url(cls, v, _):
        if isinstance(v, str):
            v = v.strip().rstrip('/')
        return v

    @field_validator('post_url', mode='before')
    def normalize_post_url(cls, v, _):
        if isinstance(v, str):
            v = v.strip().rstrip('/')
        return v

    @field_validator('data', mode='before')
    def parse_data(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        return v

    @field_validator('sheet_entries', mode='before')
    def parse_sheet_entries(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = []
        elif v is None:
            v = []
        return v


class Comment(BaseModel):
    url: str = Field(..., max_length=250)
    post_url: Optional[str] = Field(None, max_length=250)
    account_url: Optional[str] = Field(None, max_length=200)
    text: Optional[str] = None
    publication_date: Optional[datetime] = None
    data: Optional[Any] = None


class ExtractedSinglePost(BaseModel):
    post: Post
    media: list[Media] = Field(default_factory=list)
    comments: list[Comment] = Field(default_factory=list)

class ExtractedEntities(BaseModel):
    accounts: list[Account] = Field(default_factory=list)
    posts: list[ExtractedSinglePost] = Field(default_factory=list)
    comments: list[Comment] = Field(default_factory=list)

class ExtractedEntitiesFlattened(BaseModel):
    accounts: list[Account] = Field(default_factory=list)
    posts: list[Post] = Field(default_factory=list)
    media: list[Media] = Field(default_factory=list)
    comments: list[Comment] = Field(default_factory=list)

class ExtractedSingleAccount(BaseModel):
    account: Account
    posts: list[ExtractedSinglePost] = Field(default_factory=list)

class ExtractedEntitiesNested(BaseModel):
    accounts: list[ExtractedSingleAccount] = Field(default_factory=list)
    orphaned_posts: list[ExtractedSinglePost] = Field(default_factory=list)
    orphaned_media: list[Media] = Field(default_factory=list)