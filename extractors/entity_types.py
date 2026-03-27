import json
from datetime import datetime
from typing import Optional, Any, Literal

import re

from pydantic import BaseModel, Field, field_validator, model_validator

from browsing_platform.server.services.tag import ITagWithType


class EntityBase(BaseModel):
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    canonical_id: Optional[int] = None
    tags: Optional[list[ITagWithType]] = None


class Account(EntityBase):
    id_on_platform: Optional[str] = None
    url: str = Field(..., max_length=200)
    display_name: Optional[str] = Field(None, max_length=100)
    identifiers: Optional[list] = None
    bio: Optional[str] = Field(None, max_length=200)
    data: Optional[Any] = None

    @field_validator('id_on_platform', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        if isinstance(v, int):
            v = str(v)
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

    @field_validator('identifiers', mode='before')
    def parse_identifiers(cls, v, _):
        if v is None:
            return []
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = []
        return v

class Post(EntityBase):
    id_on_platform: Optional[str] = None
    url: Optional[str] = Field(None, max_length=250)
    account_id: Optional[int] = None
    account_id_on_platform: Optional[str] = Field(None, max_length=200)
    account_url: Optional[str] = Field(None, max_length=200)
    publication_date: Optional[datetime] = None
    caption: Optional[str] = None
    data: Optional[Any] = None

    @field_validator('id_on_platform', 'account_id_on_platform', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        if isinstance(v, int):
            v = str(v)
        return v

    @field_validator('url', 'account_url', mode='before')
    def normalize_url(cls, v, _):
        if isinstance(v, str):
            v = v.strip()
            if '?story_media_id=' in v:
                from urllib.parse import urlsplit, urlunsplit, parse_qs
                parts = urlsplit(v)
                qs = parse_qs(parts.query)
                story_vals = qs.get('story_media_id')
                story_val = story_vals[0] if story_vals else None
                cleaned_path = parts.path.rstrip('/')
                cleaned = urlunsplit((parts.scheme, parts.netloc, cleaned_path, '', ''))
                if story_val:
                    cleaned = f"{cleaned}?story_media_id={story_val}"
                v = cleaned
            else:
                v = v.split('?')[0].rstrip('/')
        return v

    @model_validator(mode='after')
    def derive_id_on_platform_from_url(self):
        if self.id_on_platform is None and self.url:
            # Stories URL (trailing slash already stripped by normalize_url):
            # https://www.instagram.com/stories/{username}/{pk}
            m = re.search(r'/stories/[^/]+/(\d+)', self.url)
            if m:
                self.id_on_platform = m.group(1)
        return self

    @field_validator('data', mode='before')
    def parse_data(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        return v

t_media_type = Literal['video', 'audio', 'image']

class Media(EntityBase):
    id_on_platform: Optional[str] = None
    url: str = Field(..., max_length=250)
    post_id: Optional[int] = None
    post_id_on_platform: Optional[str] = None
    post_url: Optional[str] = Field(None, max_length=250)
    local_url: Optional[str] = None
    media_type: t_media_type
    data: Optional[Any] = None
    annotation: Optional[str] = None
    thumbnail_path: Optional[str] = None
    thumbnail_status: Optional[str] = None

    @field_validator('id_on_platform', 'post_id_on_platform', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        if isinstance(v, int):
            v = str(v)
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


class Comment(EntityBase):
    id_on_platform: Optional[str] = None
    url: Optional[str] = Field(None, max_length=250)
    post_id_on_platform: Optional[str] = Field(None, max_length=250)
    post_url: Optional[str] = Field(None, max_length=250)
    account_id_on_platform: Optional[str] = Field(None, max_length=200)
    account_url: Optional[str] = Field(None, max_length=200)
    account_display_name: Optional[str] = Field(None, max_length=100)
    parent_comment_id_on_platform: Optional[str] = None
    post_id: Optional[int] = None
    account_id: Optional[int] = None
    text: Optional[str] = None
    publication_date: Optional[datetime] = None
    data: Optional[Any] = None

    @field_validator('id_on_platform', 'post_id_on_platform', 'account_id_on_platform', 'parent_comment_id_on_platform', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        if isinstance(v, int):
            v = str(v)
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


class Like(EntityBase):
    id_on_platform: Optional[str] = None
    post_id_on_platform: Optional[str] = None
    post_url: Optional[str] = Field(None, max_length=250)
    account_id_on_platform: Optional[str] = Field(None, max_length=200)
    account_url: Optional[str] = Field(None, max_length=200)
    account_display_name: Optional[str] = Field(None, max_length=100)
    post_id: Optional[int] = None
    account_id: Optional[int] = None
    data: Optional[Any] = None

    @field_validator('post_id_on_platform', 'account_id_on_platform', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        if isinstance(v, int):
            v = str(v)
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

    @model_validator(mode='after')
    def synthesize_id_on_platform(self):
        if self.id_on_platform is None:
            if self.post_id_on_platform and self.account_id_on_platform:
                self.id_on_platform = f"{self.post_id_on_platform}_{self.account_id_on_platform}"
        return self


t_relation_type = Literal['follower', 'suggested']

class AccountRelation(EntityBase):
    id_on_platform: Optional[str] = None
    follower_account_id: Optional[int] = None
    follower_account_id_on_platform: Optional[str] = Field(None, max_length=100)
    follower_account_url: Optional[str] = Field(None, max_length=200)
    follower_account_display_name: Optional[str] = Field(None, max_length=100)
    followed_account_id: Optional[int] = None
    followed_account_id_on_platform: Optional[str] = Field(None, max_length=100)
    followed_account_url: Optional[str] = Field(None, max_length=200)
    followed_account_display_name: Optional[str] = Field(None, max_length=100)
    relation_type: Optional[t_relation_type] = None
    data: Optional[Any] = None

    @field_validator('follower_account_id_on_platform', 'followed_account_id_on_platform', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        if isinstance(v, int):
            v = str(v)
        return v

    @field_validator('follower_account_url', 'followed_account_url', mode='before')
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

    @model_validator(mode='after')
    def synthesize_id_on_platform(self):
        if self.id_on_platform is None:
            a_id = self.follower_account_id_on_platform or ''
            b_id = self.followed_account_id_on_platform or ''
            rel = self.relation_type or ''
            if self.follower_account_id_on_platform and self.followed_account_id_on_platform:
                self.id_on_platform = f"{a_id}_{b_id}_{rel}"
        return self


class TaggedAccount(EntityBase):
    id_on_platform: Optional[str] = None
    tagged_account_id: Optional[int] = None
    tagged_account_id_on_platform: Optional[str] = Field(None, max_length=200)
    tagged_account_url: Optional[str] = Field(None, max_length=250)
    tagged_account_display_name: Optional[str] = Field(None, max_length=100)
    post_id: Optional[int] = None
    media_id: Optional[int] = None
    context_post_url: Optional[str] = Field(None, max_length=250)
    context_media_url: Optional[str] = Field(None, max_length=250)
    context_post_id_on_platform: Optional[str] = Field(None, max_length=250)
    context_media_id_on_platform: Optional[str] = Field(None, max_length=250)
    tag_x_position: Optional[float] = None
    tag_y_position: Optional[float] = None
    data: Optional[Any] = None

    @field_validator('tagged_account_id_on_platform', 'context_post_id_on_platform', 'context_media_id_on_platform', mode='before')
    def normalize_id_on_platform(cls, v, _):
        if isinstance(v, str):
            v = v.strip().split("_")[0]
        if isinstance(v, int):
            v = str(v)
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

    @model_validator(mode='after')
    def synthesize_id_on_platform(self):
        if self.id_on_platform is None:
            tagged_id = self.tagged_account_id_on_platform or ''
            post_id = self.context_post_id_on_platform or ''
            media_id = self.context_media_id_on_platform or ''
            if self.tagged_account_id_on_platform and (self.context_post_id_on_platform or self.context_media_id_on_platform):
                self.id_on_platform = f"{tagged_id}_{post_id}_{media_id}"
        return self


class ExtractedEntitiesFlattened(BaseModel):
    accounts: list[Account] = Field(default_factory=list)
    posts: list[Post] = Field(default_factory=list)
    media: list[Media] = Field(default_factory=list)
    comments: list[Comment] = Field(default_factory=list)
    likes: list[Like] = Field(default_factory=list)
    account_relations: list[AccountRelation] = Field(default_factory=list)
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
    account_relations: list[AccountRelation] = Field(default_factory=list)

class ExtractedEntitiesNested(BaseModel):
    accounts: list[AccountAndAssociatedEntities] = Field(default_factory=list)
    posts: list[PostAndAssociatedEntities] = Field(default_factory=list)
    media: list[MediaAndAssociatedEntities] = Field(default_factory=list)