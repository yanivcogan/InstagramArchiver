from typing import Optional

from extractors.models import StoriesFeed, CommentsConnection
from extractors.models_api_v1 import LikersApiV1
from extractors.models_graphql import ProfileTimelineGraphQL, FriendsListGraphQL, ReelsMediaConnection, \
    ClipsUserConnection
from extractors.structures_extraction_graphql import GraphQLResponse


def extract_graphql_from_response(response_json: dict) -> Optional[GraphQLResponse]:
    """
    Detects GraphQL query type by inspecting the response JSON structure.
    Does not require the X-FB-Friendly-Name request header, making it
    suitable for WACZ/WARC archives where request headers may be unavailable.
    """
    data = response_json.get("data", {})
    if not data:
        return None

    res = GraphQLResponse()

    try:
        if "xdt_api__v1__feed__user_timeline_graphql_connection" in data:
            res.profile_timeline = ProfileTimelineGraphQL(
                **data["xdt_api__v1__feed__user_timeline_graphql_connection"]
            )
    except Exception as e:
        print(f"[graphql_response] Error parsing profile_timeline: {e}")

    try:
        if "xdt_api__v1__discover__chaining" in data:
            res.friends_list = FriendsListGraphQL(**data["xdt_api__v1__discover__chaining"])
    except Exception as e:
        print(f"[graphql_response] Error parsing friends_list: {e}")

    try:
        if "xdt_api__v1__feed__reels_media__connection" in data:
            res.reels_media = ReelsMediaConnection(**data["xdt_api__v1__feed__reels_media__connection"])
    except Exception as e:
        print(f"[graphql_response] Error parsing reels_media: {e}")

    try:
        if "xdt_api__v1__feed__reels_media" in data:
            res.stories_feed = StoriesFeed(**data["xdt_api__v1__feed__reels_media"])
    except Exception as e:
        print(f"[graphql_response] Error parsing stories_feed: {e}")

    try:
        if "xdt_api__v1__clips__user__connection_v2" in data:
            res.clips_user_connection = ClipsUserConnection(
                **data["xdt_api__v1__clips__user__connection_v2"]
            )
    except Exception as e:
        print(f"[graphql_response] Error parsing clips_user_connection: {e}")

    try:
        if "xdt_api__v1__media__media_id__comments__connection" in data:
            res.comments_connection = CommentsConnection(
                **data["xdt_api__v1__media__media_id__comments__connection"]
            )
    except Exception as e:
        print(f"[graphql_response] Error parsing comments_connection: {e}")

    try:
        if "xdt_api__v1__likes__media_id__likers" in data:
            res.likes = LikersApiV1(**data["xdt_api__v1__likes__media_id__likers"])
    except Exception as e:
        print(f"[graphql_response] Error parsing likes: {e}")

    return res if any([
        res.profile_timeline,
        res.friends_list,
        res.reels_media,
        res.clips_user_connection,
        res.stories_feed,
        res.comments_connection,
        res.likes,
    ]) else None
