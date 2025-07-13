from datetime import datetime
from pathlib import Path
from typing import Optional

import pyperclip
from extractors.entity_types import ExtractedEntities, ExtractedSinglePost, Post, Account, Media, \
    ExtractedEntitiesFlattened, ExtractedEntitiesNested, ExtractedSingleAccount
from extractors.extract_photos import photos_from_har
from extractors.extract_videos import videos_from_har
from extractors.models import MediaShortcode, HighlightsReelConnection, StoriesFeed
from extractors.models_api_v1 import MediaInfoApiV1
from extractors.models_graphql import ProfileTimelineGraphQL, ReelsMediaConnection
from extractors.structures_extraction import StructureType, structures_from_har
from extractors.structures_extraction_api_v1 import ApiV1Response
from extractors.structures_extraction_graphql import GraphQLResponse
from extractors.structures_extraction_html import PageResponse
from reconcile_entities import reconcile_accounts, reconcile_posts, reconcile_media


def extract_entities_from_har(har_path: Path, download_full_video: bool = False) -> ExtractedEntitiesFlattened:
    archive_dir = har_path.parent
    videos = videos_from_har(har_path, archive_dir / "videos", download_full_video=download_full_video)
    photos = photos_from_har(har_path, archive_dir / "photos", reextract_existing_photos=download_full_video)

    local_files_map = dict()
    for video in videos:
        for track in video.tracks.values():
            if len(video.local_files):
                local_files_map[canonical_cdn_url(track.base_url) + ".mp4"] = video.local_files[0]
    for photo in photos:
        if len(photo.local_files) > 0:
            local_files_map[canonical_cdn_url(photo.url)] = photo.local_files[0]
    structures = structures_from_har(har_path)
    entities = ExtractedEntities()
    for structure in structures:
        extracted = extract_entities_from_structure(structure, local_files_map)
        entities.posts.extend(extracted.posts)
        entities.accounts.extend(extracted.accounts)
    flattened_entities = deduplicate_entities(entities)
    return flattened_entities


def nest_entities(entities: ExtractedEntitiesFlattened) -> ExtractedEntitiesNested:
    nested_accounts: list[ExtractedSingleAccount] = []
    orphaned_posts: list[ExtractedSinglePost] = []
    orphaned_media: list[Media] = []

    account_map: dict[str, ExtractedSingleAccount] = {}
    for account in entities.accounts:
        account_map[account.url] = ExtractedSingleAccount(account=account)
        nested_accounts.append(account_map[account.url])

    post_map: dict[str, ExtractedSinglePost] = {}
    for post in entities.posts:
        post_map[post.url] = ExtractedSinglePost(post=post, media=[])
        account_url = post.account_url
        if account_url in account_map:
            account_map[account_url].posts.append(post_map[post.url])
        else:
            orphaned_posts.append(post_map[post.url])

    for media in entities.media:
        if media.post_url in post_map:
            post_map[media.post_url].media.append(media)
        else:
            orphaned_media.append(media)

    return ExtractedEntitiesNested(
        accounts=nested_accounts,
        orphaned_posts=orphaned_posts,
        orphaned_media=orphaned_media
    )


def extract_entities_from_structure(structure: StructureType, local_files_map: dict[str, Path]) -> ExtractedEntities:
    entities = convert_structure_to_entities(structure)
    for post in entities.posts:
        for media in post.media:
            clean_media_url = media.url
            if clean_media_url in local_files_map:
                media.local_url = str(local_files_map[clean_media_url])
        post.media = [media for media in post.media if media.local_url]
    entities.posts = [post for post in entities.posts if
                      len(post.media) > 0 or (post.post.caption and len(post.post.caption.strip()))]
    return entities


def convert_structure_to_entities(structure: StructureType) -> ExtractedEntities:
    if isinstance(structure, GraphQLResponse):
        return graphql_to_entities(structure)
    elif isinstance(structure, ApiV1Response):
        return api_v1_to_entities(structure)
    elif isinstance(structure, PageResponse):
        return page_to_entities(structure)
    else:
        raise ValueError(f"Unsupported structure type: {type(structure)}")


def graphql_to_entities(structure: GraphQLResponse) -> ExtractedEntities:
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
                caption=item.caption.text if item.caption else None,
                data=item.model_dump()
            )
            account = Account(
                url=post.account_url,
                display_name=None,
                bio=None,
                data=highlight.user.model_dump()
            )
            media: list[Media] = [Media(
                url=canonical_cdn_url(
                    item.video_versions[0].url if item.video_versions else item.image_versions2.candidates[0].url),
                post_url=post.url,
                local_url=None,
                media_type="video" if item.video_versions else "image",
                data=item.model_dump(exclude={'carousel_media'})
            )]
            if item.carousel_media:
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
            caption=item.caption.text if item.caption else None,
            data=item.model_dump()
        )
        account = Account(
            url=post.account_url,
            display_name=None,
            bio=None,
            data=item.user.model_dump()
        )
        media: list[Media] = [Media(
            url=canonical_cdn_url(
                item.video_versions[0].url if item.video_versions else item.image_versions2.candidates[0].url),
            post_url=post.url,
            local_url=None,
            media_type="video" if item.video_versions else "image",
            data=item.model_dump(exclude={'carousel_media'})
        )]
        if item.carousel_media:
            for media_item in item.carousel_media:
                media_url = media_item.video_versions[0].url if media_item.video_versions else \
                media_item.image_versions2.candidates[0].url
                media.append(Media(
                    url=canonical_cdn_url(media_url),
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
            caption=item.caption.text if item.caption else None,
            data=item.model_dump()
        )
        account = Account(
            url=post.account_url,
            display_name=item.owner.full_name,
            bio=None,
            data=item.owner.model_dump()
        )
        media: list[Media] = [Media(
            url=canonical_cdn_url(
                item.video_versions[0].url if item.video_versions else item.image_versions2.candidates[0].url),
            post_url=post.url,
            local_url=None,
            media_type="video" if item.video_versions else "image",
            data=item.model_dump(exclude={'carousel_media'})
        )]
        extracted_posts.append(ExtractedSinglePost(
            post=post,
            media=media,
        ))
        extracted_accounts.append(account)
    return ExtractedEntities(
        accounts=extracted_accounts,
        posts=extracted_posts
    )


def page_to_entities(structure: PageResponse) -> ExtractedEntities:
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


def page_posts_to_entities(structure: MediaShortcode) -> ExtractedEntities:
    extracted_posts: list[ExtractedSinglePost] = []
    extracted_accounts: list[Account] = []
    for item in structure.items:
        post = Post(
            url="https://www.instagram.com/p/" + media_id_to_shortcode(int(item.pk)),
            account_url=f"https://www.instagram.com/{item.owner.username}/",
            publication_date=datetime.fromtimestamp(item.taken_at),
            caption=item.caption.text if item.caption else None,
            data=item.model_dump()
        )
        account: Account = Account(
            url=post.account_url,
            display_name=item.owner.full_name,
            bio=None,
            data=item.owner.model_dump()
        )
        media: list[Media] = [Media(
            url=canonical_cdn_url(
                item.video_versions[0].url if item.video_versions else item.image_versions2.candidates[0].url),
            post_url=post.url,
            local_url=None,
            media_type="video" if item.video_versions else "image",
            data=item.model_dump(exclude={'carousel_media'})
        )]
        if item.carousel_media:
            for media_item in item.carousel_media:
                url = (media_item.video_versions[0].url
                       if media_item.video_versions and len(media_item.video_versions)
                       else (
                    media_item.image_versions2.candidates[0].url
                    if media_item.image_versions2 and len(media_item.image_versions2.candidates)
                    else None
                ))
                media.append(Media(
                    url=canonical_cdn_url(url),
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


def page_highlight_reels_to_entities(structure: HighlightsReelConnection) -> ExtractedEntities:
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


def page_stories_to_entities(structure: StoriesFeed) -> ExtractedEntities:
    extracted_posts: list[ExtractedSinglePost] = []
    extracted_accounts: list[Account] = []
    reels_media = structure.reels_media[0] if structure.reels_media and len(structure.reels_media) > 0 else None
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
            caption=item.caption.text if item.caption else None,
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
    insta_filename = url.split("?")[0].split("/")[-1]
    return f"https://scontent.cdninstagram.com/v/{insta_filename}"


def media_id_to_shortcode(media_id: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    shortcode = ''
    while media_id > 0:
        media_id, remainder = divmod(media_id, 64)
        shortcode = alphabet[remainder] + shortcode
    return shortcode


def deduplicate_entities(entities: ExtractedEntities) -> ExtractedEntitiesFlattened:
    unique_accounts: dict[str, Account] = dict()
    unique_posts: dict[str, Post] = dict()
    unique_medias: dict[str, Media] = dict()

    for post in entities.posts:
        if post.post.url not in unique_posts:
            unique_posts[post.post.url] = post.post
        else:
            existing_post = unique_posts[post.post.url]
            unique_posts[post.post.url] = reconcile_posts(post.post, existing_post)
        for media in post.media:
            if media.url not in unique_medias:
                unique_medias[media.url] = media
            else:
                existing_media = unique_medias[media.url]
                unique_medias[media.url] = reconcile_media(media, existing_media)

    for account in entities.accounts:
        if account.url not in unique_accounts:
            unique_accounts[account.url] = account
        else:
            existing_account = unique_accounts[account.url]
            unique_accounts[account.url] = reconcile_accounts(account, existing_account)

    return ExtractedEntitiesFlattened(
        accounts=list(unique_accounts.values()),
        posts=list(unique_posts.values()),
        media=list(unique_medias.values())
    )


def attach_archiving_session(flattened_entities: ExtractedEntitiesFlattened,
                             archiving_session: str) -> ExtractedEntitiesFlattened:
    for account in flattened_entities.accounts:
        account.sheet_entries = [archiving_session]
    for post in flattened_entities.posts:
        post.sheet_entries = [archiving_session]
    for media in flattened_entities.media:
        media.sheet_entries = [archiving_session]
    return flattened_entities


def manual_entity_extraction():
    # Provide the path to your .har file and desired output folder
    har_file = input("Input path to HAR file: ")  # Replace with your actual HAR file
    # Strip leading and trailing whitespace as well as " " or " from the input
    har_file = har_file.strip().strip('"').strip("'")
    har_path = Path(har_file)
    entities = extract_entities_from_har(har_path)
    pyperclip.copy(entities.model_dump_json(indent=2))


if __name__ == '__main__':
    manual_entity_extraction()
