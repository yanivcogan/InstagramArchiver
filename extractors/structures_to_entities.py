from datetime import datetime
from pathlib import Path

from entity_types import ExtractedEntities, ExtractedSinglePost, Post, Account, Media
from extract_photos import photos_from_har
from extract_videos import videos_from_har
from models import MediaShortcode, HighlightsReelConnection, StoriesFeed
from models_api_v1 import MediaInfoApiV1
from models_graphql import ProfileTimelineGraphQL, ReelsMediaConnection
from structures_extraction import StructureType, structures_from_har
from structures_extraction_api_v1 import ApiV1Response
from structures_extraction_graphql import GraphQLResponse
from structures_extraction_html import PageResponse


def extract_entities_from_har(har_path: Path) -> ExtractedEntities:
    archive_dir = har_path.parent
    videos = videos_from_har(har_path, archive_dir / "videos", download_full_video=False)
    photos = photos_from_har(har_path, archive_dir / "photos")
    local_files_map = dict()
    for video in videos:
        for track in video.tracks.values():
            local_files_map[canonical_cdn_url(track.base_url)] = video.local_files[0]
    for photo in photos:
        local_files_map[canonical_cdn_url(photo.url)] = photo.local_files[0]
    structures = structures_from_har(har_path)
    entities = ExtractedEntities()
    for structure in structures:
        extracted = extract_entities_from_structure(structure, local_files_map)
        entities.posts.extend(extracted.posts)
        entities.accounts.extend(extracted.accounts)
    return entities


def extract_entities_from_structure(structure: StructureType, local_files_map: dict[str, Path]) -> ExtractedEntities:
    entities = convert_structure_to_entities(structure)
    for post in entities.posts:
        for media in post.media:
            if media.url in local_files_map:
                media.local_url = str(local_files_map[media.url])
    return entities


def convert_structure_to_entities(structure: StructureType)-> ExtractedEntities:
    if isinstance(structure, GraphQLResponse):
        return graphql_to_entities(structure)
    elif isinstance(structure, ApiV1Response):
        return api_v1_to_entities(structure)
    elif isinstance(structure, PageResponse):
        return page_to_entities(structure)
    else:
        raise ValueError(f"Unsupported structure type: {type(structure)}")


def graphql_to_entities(structure: GraphQLResponse)-> ExtractedEntities:
    entities = ExtractedEntities()
    if structure.reels_media:
        extracted = graphql_reels_media_to_entities(structure.reels_media)
        entities.posts.extend(extracted.posts)
        entities.accounts.extend(extracted.accounts)
    if structure.stories_feed:
        extracted = page_stories_to_entities(structure.stories_feed)
        entities.posts.extend(extracted.posts)
        entities.accounts.extend(extracted.accounts)
    if structure.profile_timeline:
        extracted = graphql_profile_timeline_to_entities(structure.profile_timeline)
        entities.posts.extend(extracted.posts)
        entities.accounts.extend(extracted.accounts)
    return entities


def graphql_reels_media_to_entities(structure: ReelsMediaConnection) -> ExtractedEntities:
    extracted_posts: list[ExtractedSinglePost] = []
    extracted_accounts: list[Account] = []
    for edge in structure.edges:
        highlight = edge.node
        for item in highlight.items:
            post = Post(
                url="https://www.instagram.com/p/" + media_id_to_shortcode(int(item.pk)),
                account_url=f"https://www.instagram.com/{highlight.user.username}/",
                publication_date=datetime.fromtimestamp(item.taken_at),
                caption=item.caption,
                data=item.model_dump()
            )
            account = Account(
                url=post.account_url,
                display_name=None,
                bio=None,
                data=highlight.user.model_dump()
            )
            media: list[Media] = [Media(
                url=canonical_cdn_url(item.video_versions[0].url if item.video_versions else item.image_versions2.candidates[0].url),
                post_url=post.url,
                local_url=None,
                media_type="video" if item.video_versions else "image",
                data=item.model_dump(exclude={'carousel_media'})
            )]
            for media_item in item.carousel_media:
                media.append(Media(
                    url=canonical_cdn_url(media_item.url),
                    post_url=post.url,
                    local_url=None,
                    media_type="image" if media_item.media_type == 1 else "video",
                    data=media_item.model_dump()
                ))
            extracted_posts.append(ExtractedSinglePost(
                post=post,
                media=media,
            ))
            extracted_accounts.append(account)
    return ExtractedEntities(
        accounts=extracted_accounts,
        posts=extracted_posts
    )


def graphql_profile_timeline_to_entities(structure: ProfileTimelineGraphQL) -> ExtractedEntities:
    extracted_posts: list[ExtractedSinglePost] = []
    extracted_accounts: list[Account] = []
    for edge in structure.edges:
        item = edge.node
        post = Post(
            url="https://www.instagram.com/p/" + media_id_to_shortcode(int(item.pk)),
            account_url=f"https://www.instagram.com/{item.user.username}/",
            publication_date=datetime.fromtimestamp(item.taken_at),
            caption=item.caption,
            data=item.model_dump()
        )
        account = Account(
            url=post.account_url,
            display_name=None,
            bio=None,
            data=item.user.model_dump()
        )
        media: list[Media] = [Media(
            url=canonical_cdn_url(item.video_versions[0].url if item.video_versions else item.image_versions2.candidates[0].url),
            post_url=post.url,
            local_url=None,
            media_type="video" if item.video_versions else "image",
            data=item.model_dump(exclude={'carousel_media'})
        )]
        for media_item in item.carousel_media:
            media.append(Media(
                url=canonical_cdn_url(media_item.url),
                post_url=post.url,
                local_url=None,
                media_type="image" if media_item.media_type == 1 else "video",
                data=media_item.model_dump()
            ))
        extracted_posts.append(ExtractedSinglePost(
            post=post,
            media=media,
        ))
        extracted_accounts.append(account)
    return ExtractedEntities(
        accounts=extracted_accounts,
        posts=extracted_posts
    )


def api_v1_to_entities(structure: ApiV1Response) -> ExtractedEntities:
    entities = ExtractedEntities()
    if structure.media_info:
        extracted = api_v1_media_info_to_entities(structure.media_info)
        entities.posts.extend(extracted.posts)
        entities.accounts.extend(extracted.accounts)
    return entities


def api_v1_media_info_to_entities(media_info: MediaInfoApiV1) -> ExtractedEntities:
    extracted_posts: list[ExtractedSinglePost] = []
    extracted_accounts: list[Account] = []
    for item in media_info.items:
        post = Post(
            url="https://www.instagram.com/p/" + media_id_to_shortcode(int(item.pk)),
            account_url=f"https://www.instagram.com/{item.owner.username}/",
            publication_date=datetime.fromtimestamp(item.taken_at),
            caption=item.caption,
            data=item.model_dump()
        )
        account = Account(
            url=post.account_url,
            display_name=item.owner.full_name,
            bio=None,
            data=item.owner.model_dump()
        )
        media: list[Media] = [Media(
            url=canonical_cdn_url(item.video_versions[0].url if item.video_versions else item.image_versions2.candidates[0].url),
            post_url=post.url,
            local_url=None,
            media_type="video" if item.video_versions else "image",
            data=item.model_dump(exclude={'carousel_media'})
        )]
        for media_item in getattr(item, "carousel_media", []):
            media.append(Media(
                url=canonical_cdn_url(media_item.url),
                post_url=post.url,
                local_url=None,
                media_type="image" if media_item.media_type == 1 else "video",
                data=media_item.model_dump()
            ))
        extracted_posts.append(ExtractedSinglePost(
            post=post,
            media=media,
        ))
        extracted_accounts.append(account)
    return ExtractedEntities(
        accounts=extracted_accounts,
        posts=extracted_posts
    )

def page_to_entities(structure: PageResponse)-> ExtractedEntities:
    entities = ExtractedEntities()
    if structure.posts:
        extracted = page_posts_to_entities(structure.posts)
        entities.posts.extend(extracted.posts)
        entities.accounts.extend(extracted.accounts)
    if structure.highlight_reels:
        extracted = page_highlight_reels_to_entities(structure.highlight_reels)
        entities.posts.extend(extracted.posts)
        entities.accounts.extend(extracted.accounts)
    if structure.stories:
        extracted = page_stories_to_entities(structure.stories)
        entities.posts.extend(extracted.posts)
        entities.accounts.extend(extracted.accounts)
    return entities

def page_posts_to_entities(structure: MediaShortcode)-> ExtractedEntities:
    extracted_posts:list[ExtractedSinglePost] = []
    extracted_accounts: list[Account] = []
    for item in structure.items:
        post = Post(
            url="https://www.instagram.com/p/" + media_id_to_shortcode(int(item.pk)),
            account_url=f"https://www.instagram.com/{item.owner.username}/",
            publication_date=datetime.fromtimestamp(item.taken_at),
            caption=item.caption,
            data=item.model_dump()
        )
        account: Account = Account(
            url=post.account_url,
            display_name=item.owner.full_name,
            bio=None,
            data=item.owner.model_dump()
        )
        media: list[Media] = [Media(
            url=canonical_cdn_url(item.video_versions[0].url if item.video_versions else item.image_versions2.candidates[0].url),
            post_url=post.url,
            local_url=None,
            media_type="video" if item.video_versions else "image",
            data=item.model_dump(exclude={'carousel_media'})
        )]
        for media_item in item.carousel_media:
            media.append(Media(
                url=canonical_cdn_url(media_item.url),
                post_url=post.url,
                local_url=None,
                media_type="image" if media_item == 1 else "video",
                data=media_item.model_dump()
            ))
        extracted_posts.append(ExtractedSinglePost(
            post=post,
            media=media,
        ))
        extracted_accounts.append(account)
    return ExtractedEntities(
        accounts=extracted_accounts,
        posts=extracted_posts
    )

def page_highlight_reels_to_entities(structure: HighlightsReelConnection)-> ExtractedEntities:
    extracted_posts: list[ExtractedSinglePost] = []
    extracted_accounts: list[Account] = []
    highlight = structure.edges[0].node if structure.edges else None
    if not highlight:
        return ExtractedEntities(
            accounts=extracted_accounts,
            posts=extracted_posts
        )
    account = Account(
        url=f"https://www.instagram.com/{highlight.user.username}/",
        display_name=None,
        bio=None,
        data=highlight.user.model_dump()
    )
    extracted_accounts.append(account)
    for reel in highlight.items:
        post = Post(
            url="https://www.instagram.com/p/" + media_id_to_shortcode(int(reel.pk)),
            account_url=account.url,
            publication_date=datetime.fromtimestamp(reel.taken_at),
            caption=reel.caption,
            data=reel.model_dump()
        )
        media: list[Media] = [Media(
            url=canonical_cdn_url(
                reel.video_versions[0].url if reel.video_versions else reel.image_versions2.candidates[0].url),
            post_url=post.url,
            local_url=None,
            media_type="video" if reel.video_versions else "image",
            data=reel.model_dump()
        )]
        extracted_posts.append(ExtractedSinglePost(
            post=post,
            media=media,
        ))
    return ExtractedEntities(
        accounts=extracted_accounts,
        posts=extracted_posts
    )

def page_stories_to_entities(structure: StoriesFeed)-> ExtractedEntities:
    extracted_posts: list[ExtractedSinglePost] = []
    extracted_accounts: list[Account] = []
    reels_media = structure.reels_media[0]
    if not reels_media:
        return ExtractedEntities(
            accounts=extracted_accounts,
            posts=extracted_posts
        )
    account = Account(
        url=f"https://www.instagram.com/{reels_media.user.username}/",
        display_name=None,
        bio=None,
        data=reels_media.user.model_dump()
    )
    extracted_accounts.append(account)
    for item in reels_media.items:
        post = Post(
            url="https://www.instagram.com/p/" + media_id_to_shortcode(int(item.pk)),
            account_url=account.url,
            publication_date=datetime.fromtimestamp(item.taken_at),
            caption=item.caption,
            data=item.model_dump()
        )
        media: list[Media] = [Media(
            url=canonical_cdn_url(
                item.video_versions[0].url if item.video_versions else item.image_versions2.candidates[0].url),
            post_url=post.url,
            local_url=None,
            media_type="video" if item.video_versions else "image",
            data=item.model_dump()
        )]
        extracted_posts.append(ExtractedSinglePost(
            post=post,
            media=media,
        ))
    return ExtractedEntities(
        accounts=extracted_accounts,
        posts=extracted_posts
    )

def canonical_cdn_url(url: str) -> str:
    insta_filename= url.split("?")[0].split("/")[-1]
    return f"https://scontent.cdninstagram.com/v/{insta_filename}"

def media_id_to_shortcode(media_id: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    shortcode = ''
    while media_id > 0:
        media_id, remainder = divmod(media_id, 64)
        shortcode = alphabet[remainder] + shortcode
    return shortcode