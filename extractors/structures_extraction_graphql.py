from typing import Any, Optional

from pydantic import BaseModel

from extractors.models import InstagramPost, StoriesFeed
from extractors.models_graphql import ProfileTimelineGraphQL, FriendsListGraphQL, ReelsMediaConnection, \
    ClipsUserConnection
from extractors.models_har import HarRequest


class GraphQLResponse(BaseModel):
    context: Optional[Any] = None
    profile_timeline: Optional[ProfileTimelineGraphQL] = None
    friends_list: Optional[FriendsListGraphQL] = None
    reels_media: Optional[ReelsMediaConnection] = None
    clips_user_connection: Optional[ClipsUserConnection] = None
    stories_feed: Optional[StoriesFeed] = None


def extract_data_from_graphql_entry(graphql_data: dict, req: HarRequest) -> Optional[GraphQLResponse]:
    payload = req.postData
    res = GraphQLResponse(context=payload)
    method_type = None
    for h in req.headers:
        if h.name == 'X-FB-Friendly-Name':
            method_type = h.value
            break
    if not method_type:
        return None
    if (method_type == "PolarisProfilePostsTabContentQuery_connection" or
        method_type == "PolarisProfilePostsQuery"):
        res.profile_timeline=ProfileTimelineGraphQL(**graphql_data["data"]["xdt_api__v1__feed__user_timeline_graphql_connection"])
    if method_type == "PolarisProfileSuggestedUsersWithPreloadableQuery":
        res.friends_list = FriendsListGraphQL(**graphql_data["data"]["xdt_api__v1__discover__chaining"])
    if method_type == "PolarisStoriesV3HighlightsPageQuery" or method_type == "PolarisStoriesV3HighlightsPagePaginationQuery":
        res.reels_media = ReelsMediaConnection(**graphql_data["data"]["xdt_api__v1__feed__reels_media__connection"])
    if method_type == "PolarisStoriesV3ReelPageStandaloneQuery":
        res.stories_feed = StoriesFeed(**graphql_data["data"]["xdt_api__v1__feed__reels_media"])
    if method_type == "PolarisProfileReelsTabContentQuery":
        res.clips_user_connection = ClipsUserConnection(**graphql_data["data"]["xdt_api__v1__clips__user__connection_v2"])
    return res if any([
        res.profile_timeline,
        res.friends_list,
        res.reels_media,
        res.clips_user_connection,
        res.stories_feed
    ]) else None
