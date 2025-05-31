from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Any


class InstagramCaption(BaseModel):
    created_at: int
    has_translation: Optional[bool] = None
    pk: str
    text: str

class InstagramImageCandidate(BaseModel):
    height: int
    url: str
    width: int

class InstagramImageVersions2(BaseModel):
    candidates: List[InstagramImageCandidate]

class InstagramSharingFrictionInfo(BaseModel):
    bloks_app_url: Optional[str] = None
    should_have_sharing_friction: bool

class InstagramUserTagUser(BaseModel):
    full_name: str
    id: str
    is_verified: bool
    pk: str
    profile_pic_url: str
    username: str

class InstagramUserTag(BaseModel):
    position: List[float]
    user: InstagramUserTagUser

class InstagramUserTags(BaseModel):
    in_field: Optional[List[InstagramUserTag]] = Field(None, alias="in")

    class Config:
        populate_by_name = True


class InstagramCarouselMedia(BaseModel):
    accessibility_caption: Optional[str] = None
    carousel_parent_id: str
    display_uri: Optional[str] = None
    has_liked: Optional[bool] = None
    id: str
    image_versions2: InstagramImageVersions2
    inventory_source: Optional[Any] = None
    is_dash_eligible: Optional[Any] = None
    like_count: Optional[int] = None
    link: Optional[Any] = None
    logging_info_token: Optional[Any] = None
    media_overlay_info: Optional[Any] = None
    media_type: int
    number_of_qualities: Optional[Any] = None
    organic_tracking_token: Optional[Any] = None
    original_height: int
    original_width: int
    owner: Optional[Any] = None # Could be a more specific User model if structure is known
    pk: str
    preview: Optional[str] = None
    previous_submitter: Optional[Any] = None
    sharing_friction_info: InstagramSharingFrictionInfo
    story_cta: Optional[Any] = None
    taken_at: int
    user: Optional[Any] = None # Could be a more specific User model if structure is known
    usertags: Optional[InstagramUserTags] = None
    video_dash_manifest: Optional[Any] = None
    video_versions: Optional[Any] = None

class InstagramLocation(BaseModel):
    typename: Optional[str] = Field(None, alias="__typename")
    lat: float
    lng: float
    name: str
    pk: int
    profile_pic_url: Optional[str] = None

    class Config:
        populate_by_name = True

class InstagramFriendshipStatus(BaseModel):
    following: Optional[bool] = None
    blocking: Optional[Any] = None
    followed_by: Optional[Any] = None
    incoming_request: Optional[Any] = None
    is_feed_favorite: Optional[bool] = None
    is_private: Optional[bool] = None
    is_restricted: Optional[bool] = None
    is_viewer_unconnected: Optional[Any] = None
    muting: Optional[Any] = None
    outgoing_request: Optional[Any] = None
    subscribed: Optional[Any] = None


class InstagramHdProfilePicUrlInfo(BaseModel):
    url: str

class InstagramUser(BaseModel):
    typename: Optional[str] = Field(None, alias="__typename")
    ai_agent_owner_username: Optional[Any] = None
    friendship_status: InstagramFriendshipStatus
    id: str
    is_private: bool
    is_unpublished: bool
    is_verified: bool
    pk: str
    profile_pic_url: str
    show_account_transparency_details: Optional[bool] = None
    transparency_label: Optional[Any] = None
    transparency_product: Optional[Any] = None
    transparency_product_enabled: Optional[bool] = None
    username: str
    full_name: Optional[str] = None
    hd_profile_pic_url_info: Optional[InstagramHdProfilePicUrlInfo] = None
    is_embeds_disabled: Optional[bool] = None
    latest_reel_media: Optional[int] = None
    live_broadcast_id: Optional[Any] = None
    live_broadcast_visibility: Optional[Any] = None


class InstagramPost(BaseModel):
    accessibility_caption: Optional[str] = None
    ad_id: Optional[Any] = None
    affiliate_info: Optional[Any] = None
    all_previous_submitters: Optional[List[Any]] = None
    boost_unavailable_identifier: Optional[Any] = None
    boost_unavailable_reason: Optional[Any] = None
    boosted_status: Optional[Any] = None
    can_reshare: Optional[Any] = None
    can_see_insights_as_brand: Optional[bool] = None
    can_viewer_reshare: Optional[bool] = None
    caption: Optional[InstagramCaption] = None
    caption_is_edited: Optional[bool] = None
    carousel_media: Optional[List[InstagramCarouselMedia]] = None
    carousel_media_count: Optional[int] = None
    carousel_parent_id: Optional[str] = None
    clips_attribution_info: Optional[Any] = None
    clips_metadata: Optional[Any] = None
    coauthor_producers: Optional[List[Any]] = None
    code: Optional[str] = None
    comment_count: Optional[int] = None
    commenting_disabled_for_viewer: Optional[Any] = None
    comments_disabled: Optional[Any] = None
    display_uri: Optional[str] = None # This seems to be None in the example, but often present
    facepile_top_likers: Optional[List[Any]] = None
    fb_like_count: Optional[Any] = None
    feed_demotion_control: Optional[Any] = None
    feed_recs_demotion_control: Optional[Any] = None
    follow_hashtag_info: Optional[Any] = None
    group: Optional[Any] = None
    has_audio: Optional[Any] = None
    has_liked: Optional[bool] = None
    has_viewer_saved: Optional[Any] = None
    id: str
    ig_media_sharing_disabled: Optional[bool] = None
    image_versions2: Optional[InstagramImageVersions2] = None
    inventory_source: Optional[Any] = None
    invited_coauthor_producers: Optional[List[Any]] = None
    is_dash_eligible: Optional[Any] = None
    is_paid_partnership: Optional[bool] = None
    like_and_view_counts_disabled: Optional[bool] = None
    like_count: Optional[int] = None
    link: Optional[Any] = None
    location: Optional[InstagramLocation] = None
    logging_info_token: Optional[Any] = None
    main_feed_carousel_starting_media_id: Optional[Any] = None
    media_level_comment_controls: Optional[Any] = None
    media_overlay_info: Optional[Any] = None
    media_type: int
    number_of_qualities: Optional[Any] = None
    open_carousel_submission_state: Optional[str] = None
    organic_tracking_token: Optional[str] = None
    original_height: Optional[int] = None
    original_width: Optional[int] = None
    owner: InstagramUser
    pk: str
    preview: Optional[Any] = None
    preview_comments: Optional[List[Any]] = None # Could be List[InstagramCommentPreview] if structure known
    previous_submitter: Optional[Any] = None
    product_type: Optional[str] = None
    saved_collection_ids: Optional[Any] = None
    sharing_friction_info: InstagramSharingFrictionInfo
    social_context: Optional[List[Any]] = None
    sponsor_tags: Optional[Any] = None
    story_cta: Optional[Any] = None
    taken_at: int
    top_likers: Optional[List[Any]] = None
    user: InstagramUser # This seems to be the same structure as owner in the example
    usertags: Optional[InstagramUserTags] = None
    video_dash_manifest: Optional[Any] = None
    video_versions: Optional[Any] = None # Could be List[InstagramVideoVersion] if structure known
    view_count: Optional[Any] = None
    wearable_attribution_info: Optional[Any] = None

    class Config:
        extra = "allow" # Allow fields not explicitly defined
        populate_by_name = True

class PostCommentUser(BaseModel):
    fbid_v2: str
    id: str
    is_unpublished: Optional[Any] = None
    is_verified: bool
    pk: str
    profile_pic_url: str
    username: str

class PostComment(BaseModel):
    typename: Optional[str] = Field(None, alias="__typename")
    child_comment_count: int
    comment_like_count: int
    created_at: int
    giphy_media_info: Optional[Any] = None
    has_liked_comment: bool
    has_translation: Optional[bool] = None
    is_covered: bool
    parent_comment_id: Optional[str] = None # Assuming parent_comment_id is a string if present
    pk: str
    restricted_status: Optional[Any] = None
    text: str
    user: PostCommentUser

    class Config:
        populate_by_name = True