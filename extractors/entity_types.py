from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Literal
import json

class Account(BaseModel):
    id_on_platform: Optional[str] = None
    url: str = Field(..., max_length=200)
    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=200)
    data: Optional[Any] = None

    @field_validator('id_on_platform', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        return v

    @field_validator('url', mode='before')
    def normalize_url(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split('?')[0].rstrip('/')
        return v

    @field_validator('data', mode='before')
    def parse_data(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        return v

class Post(BaseModel):
    id_on_platform: Optional[str] = None
    url: str = Field(..., max_length=250)
    account_id_on_platform: Optional[str] = Field(None, max_length=200)
    account_url: Optional[str] = Field(None, max_length=200)
    publication_date: Optional[datetime] = None
    caption: Optional[str] = None
    data: Optional[Any] = None

    @field_validator('id_on_platform', 'account_id_on_platform', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        return v

    @field_validator('url', 'account_url', mode='before')
    def normalize_url(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split('?')[0].rstrip('/')
        return v

    @field_validator('data', mode='before')
    def parse_data(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        return v

t_media_type = Literal['video', 'audio', 'image']

class Media(BaseModel):
    id_on_platform: Optional[str] = None
    url: str = Field(..., max_length=250)
    post_id_on_platform: Optional[str] = None
    post_url: Optional[str] = Field(None, max_length=250)
    local_url: Optional[str] = None
    media_type: t_media_type
    data: Optional[Any] = None

    @field_validator('id_on_platform', 'post_id_on_platform', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        return v

    @field_validator('url', 'post_url', mode='before')
    def normalize_url(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split('?')[0].rstrip('/')
        return v

    @field_validator('data', mode='before')
    def parse_data(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        return v


class Comment(BaseModel):
    id_on_platform: Optional[str] = None,
    url: str = Field(..., max_length=250)
    post_id_on_platform: str = Field(..., max_length=250)
    post_url: Optional[str] = Field(None, max_length=250)
    account_id_on_platform: Optional[str] = Field(None, max_length=200)
    account_url: Optional[str] = Field(None, max_length=200)
    text: Optional[str] = None
    publication_date: Optional[datetime] = None
    data: Optional[Any] = None

    @field_validator('id_on_platform', 'post_id_on_platform', 'account_id_on_platform', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        return v

    @field_validator('url', 'post_url', 'account_url', mode='before')
    def normalize_url(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split('?')[0].rstrip('/')
        return v

    @field_validator('data', mode='before')
    def parse_data(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        return v


class Like(BaseModel):
    id_on_platform: Optional[str] = None,
    post_id_on_platform: Optional[str] = None,
    post_url: Optional[str] = Field(None, max_length=250)
    account_id_on_platform: Optional[str] = Field(None, max_length=200)
    account_url: Optional[str] = Field(None, max_length=200)
    data: Optional[Any] = None

    @field_validator('id_on_platform', 'post_id_on_platform', 'account_id_on_platform', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        return v

    @field_validator('post_url', 'account_url', mode='before')
    def normalize_url(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split('?')[0].rstrip('/')
        return v

    @field_validator('data', mode='before')
    def parse_data(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        return v


class Follower(BaseModel):
    follower_account_id: str
    following_account_id: str
    data: Optional[Any] = None


class SuggestedAccount(BaseModel):
    context_account_id: str
    suggested_account_id: str
    data: Optional[Any] = None

    @field_validator('suggested_account_id', 'context_account_id', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        return v

    @field_validator('data', mode='before')
    def parse_data(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        return v


class TaggedAccount(BaseModel):
    tagged_account_id: Optional[str] = Field(None, max_length=200)
    tagged_account_url: Optional[str] = Field(None, max_length=250)
    context_account_id: Optional[str] = Field(None, max_length=200)
    context_post_url: Optional[str] = Field(None, max_length=250)
    context_media_url: Optional[str] = Field(None, max_length=250)
    context_post_id_on_platform: Optional[str] = Field(None, max_length=250)
    context_media_id_on_platform: Optional[str] = Field(None, max_length=250)
    data: Optional[Any] = None

    @field_validator('tagged_account_id', 'context_account_id', 'context_post_id_on_platform', 'context_media_id_on_platform', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        return v

    @field_validator('context_post_url', 'context_media_url', 'tagged_account_url', mode='before')
    def normalize_url(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split('?')[0].rstrip('/')
        return v

    @field_validator('data', mode='before')
    def parse_data(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        return v


class ExtractedEntitiesFlattened(BaseModel):
    accounts: list[Account] = Field(default_factory=list)
    posts: list[Post] = Field(default_factory=list)
    media: list[Media] = Field(default_factory=list)
    comments: list[Comment] = Field(default_factory=list)
    likes: list[Like] = Field(default_factory=list)
    followers: list[Follower] = Field(default_factory=list)
    suggested_accounts: list[SuggestedAccount] = Field(default_factory=list)
    tagged_accounts: list[TaggedAccount] = Field(default_factory=list)

class MediaAndAssociatedEntities(Media):
    media_parent_post: Optional['PostAndAssociatedEntities'] = None

class PostAndAssociatedEntities(Post):
    post_author: Optional['AccountAndAssociatedEntities'] = None
    post_media: list['MediaAndAssociatedEntities'] = Field(default_factory=list)
    post_comments: list[Comment] = Field(default_factory=list)
    post_likes: list[Like] = Field(default_factory=list)
    post_tagged_accounts: list[TaggedAccount] = Field(default_factory=list)

class AccountAndAssociatedEntities(Account):
    account_posts: list['PostAndAssociatedEntities'] = Field(default_factory=list)
    account_followers: list[Follower] = Field(default_factory=list)
    account_suggested_accounts: list[SuggestedAccount] = Field(default_factory=list)

class ExtractedEntitiesNested(BaseModel):
    accounts: list[AccountAndAssociatedEntities] = Field(default_factory=list)
    posts: list[PostAndAssociatedEntities] = Field(default_factory=list)
    media: list[MediaAndAssociatedEntities] = Field(default_factory=list)