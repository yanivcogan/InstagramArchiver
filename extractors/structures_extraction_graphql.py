from typing import Any, Optional

from pydantic import BaseModel

from extractors.models import InstagramPost, StoriesFeed
from extractors.models_graphql import ProfileTimelineGraphQL, FriendsListGraphQL, ReelsMediaConnection, \
    ClipsUserConnection
from extractors.models_har import HarRequest


class GraphQLResponse(BaseModel):
    profile_timeline: Optional[ProfileTimelineGraphQL] = None
    friends_list: Optional[FriendsListGraphQL] = None
    reels_media: Optional[ReelsMediaConnection] = None
    clips_user_connection: Optional[ClipsUserConnection] = None
    stories_feed: Optional[StoriesFeed] = None


def extract_data_from_graphql_entry(graphql_data: dict, req: HarRequest) -> Optional[GraphQLResponse]:
    res = None
    for h in req.headers:
        if (h.name == "PolarisProfilePostsTabContentQuery_connection" or
            h.name == "PolarisProfilePostsQuery"):
            res = GraphQLResponse(profile_timeline=ProfileTimelineGraphQL(**graphql_data["data"]["xdt_api__v1__feed__user_timeline_graphql_connection"]))
        if h.name == "PolarisProfileSuggestedUsersWithPreloadableQuery":
            res = GraphQLResponse(friends_list=FriendsListGraphQL(**graphql_data["data"]["xdt_api__v1__discover__chaining"]))
        if h.name == "PolarisStoriesV3HighlightsPageQuery":
            res = GraphQLResponse(reels_media=ReelsMediaConnection(**graphql_data["data"]["xdt_api__v1__feed__reels_media__connection"]))
        if h.name == "PolarisStoriesV3ReelPageStandaloneQuery":
            res = GraphQLResponse(stories_feed=StoriesFeed(**graphql_data["data"]["xdt_api__v1__feed__reels_media"]))
        if h.name == "PolarisProfileReelsTabContentQuery":
            res = GraphQLResponse(clips_user_connection=ClipsUserConnection(**graphql_data["data"]["xdt_api__v1__clips__user__connection_v2"]))
    return res
