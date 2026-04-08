import base64
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Callable, TypeVar
from urllib import parse as urllib_parse

import ijson
from pydantic import BaseModel

from extractors.entity_types import Post, Account, Media, \
    ExtractedEntitiesFlattened, Comment, Like, AccountRelation, \
    TaggedAccount, ExtractedEntitiesNested, AccountAndAssociatedEntities, PostAndAssociatedEntities, \
    MediaAndAssociatedEntities
from extractors.extract_photos import acquire_photos, PhotoAcquisitionConfig, Photo, \
    _is_image_request, extract_xpv_asset_id as _extract_photo_asset_id
from extractors.extract_videos import acquire_videos, VideoAcquisitionConfig, Video, \
    MediaTrack, MediaSegment, extract_xpv_asset_id as _extract_video_xpv_asset_id
from extractors.models import MediaShortcode, HighlightsReelConnection, StoriesFeed, CommentsConnection
from extractors.models_api_v1 import MediaInfoApiV1, CommentsApiV1, LikersApiV1, FriendshipsApiV1
from extractors.models_graphql import ProfileTimelineGraphQL, ReelsMediaConnection, FriendsListGraphQL
from extractors.models_har import HarRequest
from extractors.reconcile_entities import reconcile_accounts, reconcile_posts, reconcile_media
from extractors.structures_extraction import StructureType
from extractors.structures_extraction_api_v1 import ApiV1Response, ApiV1Context, extract_data_from_api_v1_entry
from extractors.structures_extraction_graphql import extract_graphql_from_response, GraphQLResponse
from extractors.structures_extraction_html import PageResponse, extract_data_from_html_entry


class ExtractedHarData(BaseModel):
    structures: list[StructureType]
    videos: list[Video]
    photos: list[Photo]


def _scan_har_once(har_path: Path) -> tuple[list[StructureType], list[Video], list[Photo]]:
    """
    Single streaming pass over a HAR file that simultaneously extracts:
    - structures (GraphQL / API v1 / HTML responses)
    - video segment maps (.mp4 entries)
    - photo maps (image entries)

    Replaces three separate ijson passes with one, roughly tripling parse speed.
    """
    structures: list[StructureType] = []
    videos_dict: dict[str, Video] = {}
    photos_dict: dict = {}  # keys are str (filename) or int (hash fallback)

    with open(har_path, 'rb') as f:
        for entry in ijson.items(f, 'log.entries.item'):
            url: str = entry['request']['url']
            content: dict = entry['response']['content']
            mime: str = content.get('mimeType', '')

            # --- Structures (GraphQL, API v1, HTML) ---
            try:
                if 'graphql/query' in url:
                    res_json: Optional[str] = content.get('text')
                    if res_json:
                        req = HarRequest(**entry['request'])
                        ctx = {p['name']: p['value'] for p in
                               req.postData.params} if req.postData and req.postData.params else {}
                        structure = extract_graphql_from_response(json.loads(res_json), context=ctx)
                        if structure:
                            structures.append(structure)
                elif 'instagram.com/api/v1/media/' in url and not mime.startswith('text/html'):
                    res_json: Optional[str] = content.get('text')
                    if res_json:
                        structure = extract_data_from_api_v1_entry(json.loads(res_json), HarRequest(**entry['request']))
                        if structure:
                            structures.append(structure)
                elif mime.startswith('text/html'):
                    html_text: Optional[str] = content.get('text')
                    if html_text:
                        structure = extract_data_from_html_entry(html_text, HarRequest(**entry['request']))
                        if structure:
                            structures.append(structure)
            except Exception as e:
                print(f"Error processing structures entry: {e}")
                traceback.print_exc()

            # --- Video segment maps (.mp4 entries with base64 content) ---
            try:
                if '.mp4' in url and 'text' in content:
                    base_url = url.split('.mp4')[0]
                    full_url = str(urllib_parse.urlunparse(
                        urllib_parse.urlparse(url)._replace(
                            query='&'.join(
                                f"{k}={v[0]}" if len(v) == 1 else '&'.join(f"{k}={i}" for i in v)
                                for k, v in urllib_parse.parse_qs(urllib_parse.urlparse(url).query).items()
                                if k not in ('bytestart', 'byteend')
                            )
                        )
                    ))
                    xpv_asset_id = _extract_video_xpv_asset_id(url)
                    filename = base_url.split('/')[-1]
                    start = end = None
                    if 'bytestart=' in url:
                        start = int(url.split('bytestart=')[1].split('&')[0])
                    if 'byteend=' in url:
                        end = int(url.split('byteend=')[1].split('&')[0])
                    segment_data = base64.b64decode(content['text'])
                    if xpv_asset_id:
                        if xpv_asset_id not in videos_dict:
                            videos_dict[xpv_asset_id] = Video(xpv_asset_id=xpv_asset_id, fetched_tracks={})
                        if filename not in videos_dict[xpv_asset_id].fetched_tracks:
                            videos_dict[xpv_asset_id].fetched_tracks[filename] = MediaTrack(
                                base_url=base_url, full_url=full_url, segments=[]
                            )
                        videos_dict[xpv_asset_id].fetched_tracks[filename].segments.append(
                            MediaSegment(start=start, end=end, data=segment_data)
                        )
            except Exception as e:
                print(f"Error processing video entry: {e}")
                traceback.print_exc()

            # --- Photo maps (image content entries) ---
            try:
                if _is_image_request(url) and 'text' in content:
                    try:
                        img_data = base64.b64decode(content['text'])
                    except Exception:
                        pass
                    else:
                        asset_id = _extract_photo_asset_id(url) or hash(url)
                        img_filename = url.split('/')[-1].split('?')[0]
                        if asset_id not in photos_dict:
                            photos_dict[asset_id] = Photo(asset_id=str(asset_id), fetched_assets={}, url=url)
                        photos_dict[asset_id].fetched_assets[img_filename] = img_data
            except Exception:
                pass

    return structures, list(videos_dict.values()), list(photos_dict.values())


def extract_data_from_har(
        har_path: Path,
        video_acquisition_config: VideoAcquisitionConfig = VideoAcquisitionConfig(
            download_missing=True, download_media_not_in_structures=True, download_unfetched_media=True,
            download_full_versions_of_fetched_media=True, download_highest_quality_assets_from_structures=True
        ),
        photo_acquisition_config: PhotoAcquisitionConfig = PhotoAcquisitionConfig(
            download_missing=True, download_media_not_in_structures=True, download_unfetched_media=True,
            download_highest_quality_assets_from_structures=True
        )
) -> ExtractedHarData:
    archive_dir = har_path.parent

    structures, har_video_maps, har_photo_maps = _scan_har_once(har_path)

    videos = acquire_videos(
        har_path,
        archive_dir / "videos",
        structures=structures,
        config=video_acquisition_config,
        har_video_maps=har_video_maps,
    )

    photos = acquire_photos(
        har_path,
        archive_dir / "photos",
        structures=structures,
        config=photo_acquisition_config,
        har_photo_maps=har_photo_maps,
    )

    return ExtractedHarData(
        structures=structures,
        videos=videos,
        photos=photos
    )


def har_data_to_entities(
        archive_path: Path,
        structures: list[StructureType],
        videos: list[Video],
        photos: list[Photo],
) -> ExtractedEntitiesFlattened:
    archive_dir = archive_path.parent
    local_files_map = dict()
    for video in videos:
        if video.fetched_tracks:
            for track in video.fetched_tracks.values():
                if video.local_files and len(video.local_files):
                    local_files_map[canonical_cdn_url(track.base_url) + ".mp4"] = video.local_files[0]
        if video.full_asset and video.local_files and len(video.local_files):
            local_files_map[canonical_cdn_url(video.full_asset)] = video.local_files[0]
    for photo in photos:
        if photo.local_files and len(photo.local_files) > 0:
            local_files_map[canonical_cdn_url(photo.url)] = photo.local_files[0]

    entities = ExtractedEntitiesFlattened(
        accounts=[], posts=[], media=[], comments=[], likes=[], account_relations=[], tagged_accounts=[]
    )
    for structure in structures:
        try:
            extend_flattened_entities(entities, convert_structure_to_entities(structure))
        except Exception as e:
            print(f"Error converting structure to entities: {e}")
            print(traceback.format_exc())
            continue
    flattened_entities = deduplicate_entities(entities)
    attach_media_to_entities(flattened_entities, local_files_map, archive_dir)
    return flattened_entities


def extract_entities_from_har(
        har_path: Path,
        video_acquisition_config: VideoAcquisitionConfig = VideoAcquisitionConfig(
            download_missing=True, download_media_not_in_structures=True, download_unfetched_media=True,
            download_full_versions_of_fetched_media=True, download_highest_quality_assets_from_structures=True
        ),
        photo_acquisition_config: PhotoAcquisitionConfig = PhotoAcquisitionConfig(
            download_missing=True, download_media_not_in_structures=True, download_unfetched_media=True,
            download_highest_quality_assets_from_structures=True
        )
) -> ExtractedEntitiesFlattened:
    har_data = extract_data_from_har(
        har_path,
        video_acquisition_config=video_acquisition_config,
        photo_acquisition_config=photo_acquisition_config
    )
    flattened_entities = har_data_to_entities(
        har_path,
        har_data.structures,
        har_data.videos,
        har_data.photos
    )
    return flattened_entities


def nest_entities_from_archive_session(entities: ExtractedEntitiesFlattened) -> ExtractedEntitiesNested:
    nested_accounts: list[AccountAndAssociatedEntities] = []
    orphaned_posts: list[PostAndAssociatedEntities] = []
    orphaned_media: list[MediaAndAssociatedEntities] = []

    account_map: dict[str, AccountAndAssociatedEntities] = {}
    for account in entities.accounts:
        account_entity = AccountAndAssociatedEntities(
            **account.model_dump(),
            account_posts=[],
            account_relations=[]
        )
        account_url = account.url
        if account_url:
            account_map[account_url] = account_entity
        nested_accounts.append(account_entity)

    post_map: dict[str, PostAndAssociatedEntities] = {}
    for post in entities.posts:
        post_entity = PostAndAssociatedEntities(
            **post.model_dump(),
            post_media=[],
            post_comments=[],
            post_likes=[],
            post_tagged_accounts=[],
            post_author=None
        )
        account_url = post.account_url
        if account_url is not None and account_url in account_map:
            post_entity.post_author = account_map[account_url]
            account_map[account_url].account_posts.append(post_entity)
        else:
            orphaned_posts.append(post_entity)
        if post.id_on_platform is not None:
            post_map[post.id_on_platform] = post_entity

    for media in entities.media:
        if media.post_id_on_platform is not None and media.post_id_on_platform in post_map:
            post_map[media.post_id_on_platform].post_media.append(MediaAndAssociatedEntities(
                **media.model_dump(),
                media_parent_post=post_map[media.post_id_on_platform]
            ))
        else:
            orphaned_media.append(MediaAndAssociatedEntities(
                **media.model_dump(),
                media_parent_post=None
            ))

    return ExtractedEntitiesNested(
        accounts=nested_accounts,
        posts=orphaned_posts,
        media=orphaned_media
    )


def attach_media_to_entities(
        entities: ExtractedEntitiesFlattened,
        local_files_map: dict[str, Path],
        archive_dir: Path
) -> None:
    for media in entities.media:
        clean_media_url = media.url_suffix
        if clean_media_url is not None and clean_media_url in local_files_map:
            local_media_url = local_files_map[clean_media_url]
            relative_path = local_media_url.relative_to(archive_dir)
            media.local_url = str(relative_path)
    # TODO: filter out media without local files?


def convert_structure_to_entities(structure: StructureType) -> ExtractedEntitiesFlattened:
    if isinstance(structure, GraphQLResponse):
        return graphql_to_entities(structure)
    elif isinstance(structure, ApiV1Response):
        return api_v1_to_entities(structure)
    elif isinstance(structure, PageResponse):
        return page_to_entities(structure)
    else:
        raise ValueError(f"Unsupported structure type: {type(structure)}")


def extend_flattened_entities(
        entities_1: ExtractedEntitiesFlattened,
        entities_2: ExtractedEntitiesFlattened
) -> None:
    entities_1.accounts.extend(entities_2.accounts)
    entities_1.posts.extend(entities_2.posts)
    entities_1.media.extend(entities_2.media)
    entities_1.comments.extend(entities_2.comments)
    entities_1.likes.extend(entities_2.likes)
    entities_1.account_relations.extend(entities_2.account_relations)
    entities_1.tagged_accounts.extend(entities_2.tagged_accounts)


def graphql_to_entities(structure: GraphQLResponse) -> ExtractedEntitiesFlattened:
    entities = ExtractedEntitiesFlattened(
        accounts=[], posts=[], media=[], comments=[], likes=[], account_relations=[], tagged_accounts=[]
    )
    if structure.reels_media:
        try:
            extend_flattened_entities(entities, graphql_reels_media_to_entities(structure.reels_media))
        except Exception:
            pass
    if structure.stories_feed:
        try:
            extend_flattened_entities(entities, page_stories_to_entities(structure.stories_feed))
        except Exception:
            pass
    if structure.profile_timeline:
        try:
            extend_flattened_entities(entities, graphql_profile_timeline_to_entities(structure.profile_timeline))
        except Exception:
            pass
    if structure.comments_connection:
        try:
            extend_flattened_entities(
                entities,
                graphql_comments_to_entities(structure.comments_connection, structure.context)
            )
        except Exception:
            pass
    if structure.likes:
        try:
            extend_flattened_entities(entities, graphql_likes_to_entities(structure.likes, structure.context))
        except Exception:
            pass
    if structure.friends_list:
        try:
            extend_flattened_entities(entities,
                                      graphql_suggested_accounts_to_entities(structure.friends_list, structure.context))
        except Exception:
            pass
    return entities


def graphql_reels_media_to_entities(structure: ReelsMediaConnection) -> ExtractedEntitiesFlattened:
    extracted_accounts: list[Account] = []
    extracted_posts: list[Post] = []
    extracted_media: list[Media] = []
    extracted_tagged_accounts: list[TaggedAccount] = []
    for edge in structure.edges:
        highlight = edge.node
        highlight_id = highlight.id.split(":")[-1]
        for item in highlight.items:
            account = Account(
                id_on_platform=highlight.user.id,
                url_suffix=f"{highlight.user.username}/",
                display_name=None,
                bio=None,
                data=highlight.user.model_dump(),
                platform="instagram"
            )
            extracted_accounts.append(account)
            post = Post(
                id_on_platform=item.pk or item.id,
                url_suffix=f"s/{highlight_id}/?story_media_id={item.pk or item.id}",
                account_id_on_platform=account.id_on_platform,
                account_url_suffix=account.url_suffix,
                publication_date=datetime.fromtimestamp(item.taken_at, timezone.utc),
                caption=item.caption.text if item.caption else None,
                data=item.model_dump(),
                platform="instagram"
            )
            extracted_posts.append(post)
            item_asset_url = (item.video_versions[0].url if item.video_versions
                              else (item.image_versions2.candidates[0].url
                                    if item.image_versions2 and item.image_versions2.candidates else None))
            extracted_media.append(Media(
                id_on_platform=item.id,
                url_suffix=canonical_cdn_url(item_asset_url) if item_asset_url else None,
                post_id_on_platform=post.id_on_platform,
                post_url_suffix=post.url_suffix,
                local_url=None,
                media_type="video" if item.video_versions else "image",
                data=item.model_dump(exclude={'carousel_media'}),
                platform="instagram"
            ))
            if item.carousel_media:
                for media_item in item.carousel_media:
                    carousel_asset_url = (media_item.video_versions[0].url if media_item.video_versions
                                          else (media_item.image_versions2.candidates[0].url
                                                if media_item.image_versions2 and media_item.image_versions2.candidates else None))
                    media_url = canonical_cdn_url(carousel_asset_url) if carousel_asset_url else None
                    extracted_media.append(Media(
                        id_on_platform=media_item.id,
                        url_suffix=media_url,
                        post_id_on_platform=post.id_on_platform,
                        post_url_suffix=post.url_suffix,
                        local_url=None,
                        media_type="image" if media_item.media_type == 1 else "video",
                        data=media_item.model_dump(),
                        platform="instagram"
                    ))
                    if media_item.usertags and media_item.usertags.in_field:
                        for tag in media_item.usertags.in_field:
                            extracted_tagged_accounts.append(TaggedAccount(
                                tagged_account_id_on_platform=tag.user.id,
                                tagged_account_url_suffix=f"{tag.user.username}/",
                                context_post_url_suffix=post.url_suffix,
                                context_media_url_suffix=media_url,
                                context_post_id_on_platform=post.id_on_platform,
                                context_media_id_on_platform=media_item.id,
                                data=None,
                                platform="instagram"
                            ))
                            extracted_accounts.append(Account(
                                id_on_platform=tag.user.id,
                                url_suffix=f"{tag.user.username}/",
                                display_name=tag.user.full_name,
                                bio=None,
                                data=tag.user.model_dump(),
                                platform="instagram"
                            ))
    return ExtractedEntitiesFlattened(
        accounts=extracted_accounts,
        posts=extracted_posts,
        media=extracted_media,
        tagged_accounts=extracted_tagged_accounts,
        comments=[], likes=[], account_relations=[]
    )


def graphql_profile_timeline_to_entities(structure: ProfileTimelineGraphQL) -> ExtractedEntitiesFlattened:
    extracted_accounts: list[Account] = []
    extracted_posts: list[Post] = []
    extracted_media: list[Media] = []
    extracted_tagged_accounts: list[TaggedAccount] = []

    for edge in structure.edges:
        item = edge.node
        if not item.user or not (item.pk or item.id):
            continue
        account = Account(
            id_on_platform=item.user.id,
            url_suffix=f"{item.user.username}/",
            display_name=None,
            bio=None,
            data=item.user.model_dump(),
            platform="instagram"
        )
        extracted_accounts.append(account)
        post_pk = item.pk or item.id
        post_code = item.code or (media_id_to_shortcode(int(post_pk)) if post_pk else None)
        post = Post(
            id_on_platform=item.pk or item.id,
            url_suffix=f"p/{post_code}" if post_code else None,
            account_id_on_platform=item.user.id,
            account_url_suffix=account.url_suffix,
            publication_date=datetime.fromtimestamp(item.taken_at, timezone.utc) if item.taken_at else None,
            caption=item.caption.text if item.caption else None,
            data=item.model_dump(),
            platform="instagram"
        )
        extracted_posts.append(post)
        if item.usertags and item.usertags.in_field:
            for tag in item.usertags.in_field:
                extracted_tagged_accounts.append(TaggedAccount(
                    tagged_account_id_on_platform=tag.user.id,
                    tagged_account_url_suffix=f"{tag.user.username}/",
                    context_post_url_suffix=post.url_suffix,
                    context_media_url_suffix=None,
                    context_post_id_on_platform=post.id_on_platform,
                    context_media_id_on_platform=None,
                    data=None,
                    platform="instagram"
                ))
                extracted_accounts.append(Account(
                    id_on_platform=tag.user.id,
                    url_suffix=f"{tag.user.username}/",
                    display_name=tag.user.full_name,
                    bio=None,
                    data=tag.user.model_dump(),
                    platform="instagram"
                ))
        asset_url = item.video_versions[0].url if item.video_versions else \
            (item.image_versions2.candidates[
                 0].url if item.image_versions2 and item.image_versions2.candidates else None)
        extracted_media.append(Media(
            id_on_platform=item.id,
            url_suffix=canonical_cdn_url(asset_url) if asset_url else None,
            post_id_on_platform=post.id_on_platform,
            post_url_suffix=post.url_suffix,
            local_url=None,
            media_type="video" if item.video_versions else "image",
            data=item.model_dump(exclude={'carousel_media'}),
            platform="instagram"
        ))
        if item.carousel_media:
            for media_item in item.carousel_media:
                media_url = media_item.video_versions[0].url if media_item.video_versions else \
                    (media_item.image_versions2.candidates[
                         0].url if media_item.image_versions2 and media_item.image_versions2.candidates else None)
                media_url_suffix = canonical_cdn_url(media_url) if media_url else None
                extracted_media.append(Media(
                    id_on_platform=media_item.id,
                    url_suffix=media_url_suffix,
                    post_id_on_platform=post.id_on_platform,
                    post_url_suffix=post.url_suffix,
                    local_url=None,
                    media_type="image" if media_item.media_type == 1 else "video",
                    data=media_item.model_dump(),
                    platform="instagram"
                ))
                if media_item.usertags and media_item.usertags.in_field:
                    for tag in media_item.usertags.in_field:
                        extracted_tagged_accounts.append(TaggedAccount(
                            tagged_account_id_on_platform=tag.user.id,
                            tagged_account_url_suffix=f"{tag.user.username}/",
                            context_post_url_suffix=post.url_suffix,
                            context_media_url_suffix=media_url_suffix,
                            context_post_id_on_platform=post.id_on_platform,
                            context_media_id_on_platform=media_item.id,
                            data=None,
                            platform="instagram"
                        ))
                        extracted_accounts.append(Account(
                            id_on_platform=tag.user.id,
                            url_suffix=f"{tag.user.username}/",
                            display_name=tag.user.full_name,
                            bio=None,
                            data=tag.user.model_dump(),
                            platform="instagram"
                        ))
    return ExtractedEntitiesFlattened(
        accounts=extracted_accounts,
        posts=extracted_posts,
        media=extracted_media,
        tagged_accounts=extracted_tagged_accounts,
        comments=[], likes=[], account_relations=[]
    )


def graphql_comments_to_entities(structure: CommentsConnection, context: Any) -> ExtractedEntitiesFlattened:
    variables_raw = context.get('variables', '{}') if isinstance(context, dict) else '{}'
    variables = json.loads(variables_raw) if isinstance(variables_raw, str) else variables_raw
    post_pk: Optional[str] = variables.get('media_id', None)
    post_url = f"p/{media_id_to_shortcode(int(post_pk))}/" if post_pk else None
    extracted_comments: list[Comment] = []
    extracted_accounts: list[Account] = []
    for e in structure.edges:
        c = e.node
        if c.user:
            extracted_accounts.append(Account(
                id_on_platform=c.user.id,
                url_suffix=f"{c.user.username}/",
                display_name=None,
                bio=None,
                data=c.user.model_dump(),
                platform="instagram"
            ))
        comment = Comment(
            id_on_platform=c.pk,
            url_suffix=f"{post_url}c/{c.pk}/" if post_url else None,
            post_id_on_platform=post_pk,
            post_url_suffix=post_url,
            account_id_on_platform=c.user.pk if c.user else None,
            account_url_suffix=f"{c.user.username}/" if c.user else None,
            text=c.text,
            parent_comment_id_on_platform=c.parent_comment_id,
            publication_date=datetime.fromtimestamp(c.created_at) if c.created_at else None,
            data=c.model_dump(),
            platform="instagram"
        )
        extracted_comments.append(comment)
    return ExtractedEntitiesFlattened(
        comments=extracted_comments,
        accounts=extracted_accounts,
        likes=[], account_relations=[], tagged_accounts=[], media=[], posts=[]
    )


def graphql_likes_to_entities(structure: LikersApiV1, context: Any) -> ExtractedEntitiesFlattened:
    variables_raw = context.get('variables', '{}') if isinstance(context, dict) else '{}'
    variables = json.loads(variables_raw) if isinstance(variables_raw, str) else variables_raw
    post_pk: Optional[str] = variables.get('media_id', None)
    post_url = f"p/{media_id_to_shortcode(int(post_pk))}/" if post_pk else None
    extracted_likes: list[Like] = []
    extracted_accounts: list[Account] = []
    for u in structure.users:
        like = Like(
            id_on_platform=None,
            post_id_on_platform=post_pk,
            post_url_suffix=post_url,
            account_id_on_platform=u.pk,
            account_url_suffix=f"{u.username}/",
            data=u.model_dump(),
            platform="instagram"
        )
        extracted_likes.append(like)
        extracted_accounts.append(Account(
            id_on_platform=u.pk,
            url_suffix=like.account_url_suffix,
            display_name=u.full_name,
            bio=None,
            data=u.model_dump(),
            platform="instagram"
        ))
    return ExtractedEntitiesFlattened(
        likes=extracted_likes,
        accounts=extracted_accounts,
        comments=[], account_relations=[], tagged_accounts=[], media=[], posts=[]
    )


def graphql_suggested_accounts_to_entities(structure: FriendsListGraphQL, context: Any) -> ExtractedEntitiesFlattened:
    variables = context.get('variables', '{}') if isinstance(context, dict) else '{}'
    variables = json.loads(variables)
    target_account_id: Optional[str] = variables.get('target_id', None)
    extracted_account_relations: list[AccountRelation] = []
    extracted_accounts: list[Account] = []
    for u in structure.users:
        account = Account(
            url_suffix=f"{u.username}/",
            display_name=u.full_name,
            bio=None,
            id_on_platform=u.id,
            data=u.model_dump(),
            platform="instagram"
        )
        extracted_accounts.append(account)
        relation = AccountRelation(
            follower_account_id_on_platform=target_account_id,
            followed_account_id_on_platform=u.id,
            followed_account_url_suffix=f"{u.username}/",
            relation_type='suggested',
            data=None,
            platform="instagram"
        )
        extracted_account_relations.append(relation)
    return ExtractedEntitiesFlattened(
        account_relations=extracted_account_relations,
        accounts=extracted_accounts,
        comments=[], likes=[], tagged_accounts=[], media=[], posts=[]
    )


def api_v1_to_entities(structure: ApiV1Response) -> ExtractedEntitiesFlattened:
    entities = ExtractedEntitiesFlattened(
        accounts=[], posts=[], media=[], comments=[], likes=[], account_relations=[], tagged_accounts=[]
    )
    if structure.media_info:
        extend_flattened_entities(entities, api_v1_media_info_to_entities(structure.media_info))
    context = structure.context or ApiV1Context()
    if structure.comments:
        extend_flattened_entities(entities, api_v1_comments_to_entities(structure.comments, context))
    if structure.likers:
        extend_flattened_entities(entities, api_v1_likes_to_entities(structure.likers, context))
    if structure.friendships:
        extend_flattened_entities(entities, api_v1_friendships_to_entities(structure.friendships, context))
    return entities


def api_v1_media_info_to_entities(media_info: MediaInfoApiV1) -> ExtractedEntitiesFlattened:
    extracted_posts: list[Post] = []
    extracted_accounts: list[Account] = []
    extracted_tagged_accounts: list[TaggedAccount] = []
    extracted_media: list[Media] = []
    for item in media_info.items:
        _username = item.user.username or item.owner.username
        account = Account(
            id_on_platform=item.user.id or item.owner.id,
            url_suffix=f"{_username}/" if _username else (
                f"id:{item.user.id or item.owner.id}" if (item.user.id or item.owner.id) else None),
            display_name=item.user.full_name or item.owner.full_name,
            bio=None,
            data=item.user.model_dump(),
            platform="instagram"
        )
        extracted_accounts.append(account)
        post = Post(
            id_on_platform=item.pk or item.id,
            url_suffix="p/" + (item.code or media_id_to_shortcode(int(item.pk))),
            account_id_on_platform=account.id_on_platform,
            account_url_suffix=account.url_suffix,
            publication_date=datetime.fromtimestamp(item.taken_at, timezone.utc),
            caption=item.caption.text if item.caption else None,
            data=item.model_dump(),
            platform="instagram"
        )
        extracted_posts.append(post)
        media_asset_url = (item.video_versions[0].url if item.video_versions
                           else (item.image_versions2.candidates[0].url
                                 if item.image_versions2 and item.image_versions2.candidates else None))
        extracted_media.append(Media(
            id_on_platform=item.id,
            url_suffix=canonical_cdn_url(media_asset_url) if media_asset_url else None,
            post_id_on_platform=post.id_on_platform,
            post_url_suffix=post.url_suffix,
            local_url=None,
            media_type="video" if item.video_versions else "image",
            data=item.model_dump(),
            platform="instagram"
        ))
        if item.usertags and item.usertags.in_field:
            for tag in item.usertags.in_field:
                extracted_tagged_accounts.append(TaggedAccount(
                    tagged_account_id_on_platform=tag.user.id,
                    tagged_account_url_suffix=f"{tag.user.username}/",
                    context_post_url_suffix=post.url_suffix,
                    context_media_url_suffix=None,
                    context_post_id_on_platform=post.id_on_platform,
                    context_media_id_on_platform=None,
                    tag_x_position=tag.position[0] if tag.position and len(tag.position) > 0 else None,
                    tag_y_position=tag.position[1] if tag.position and len(tag.position) > 1 else None,
                    data=None,
                    platform="instagram"
                ))
                extracted_accounts.append(Account(
                    id_on_platform=tag.user.id,
                    url_suffix=f"{tag.user.username}/",
                    display_name=tag.user.full_name,
                    bio=None,
                    data=tag.user.model_dump(),
                    platform="instagram"
                ))
    return ExtractedEntitiesFlattened(
        accounts=extracted_accounts,
        posts=extracted_posts,
        media=extracted_media,
        tagged_accounts=extracted_tagged_accounts,
        comments=[], likes=[], account_relations=[]
    )


def api_v1_comments_to_entities(comments_insta: CommentsApiV1, context: ApiV1Context) -> ExtractedEntitiesFlattened:
    post_pk: Optional[str] = context.media_id
    comments: list[Comment] = []
    accounts: list[Account] = []

    post_url = f"p/{media_id_to_shortcode(int(post_pk))}/" if post_pk else None
    for c in comments_insta.comments:
        if c.user:
            accounts.append(Account(
                id_on_platform=c.user.id,
                url_suffix=f"{c.user.username}/",
                display_name=None,
                bio=None,
                data=c.user.model_dump(),
                platform="instagram"
            ))
        comment = Comment(
            id_on_platform=c.pk,
            url_suffix=f"{post_url}c/{c.pk}/" if post_url else None,
            post_id_on_platform=post_pk,
            post_url_suffix=post_url,
            account_id_on_platform=c.user.id if c.user else None,
            account_url_suffix=f"{c.user.username}/" if c.user else None,
            text=c.text,
            publication_date=datetime.fromtimestamp(c.created_at) if c.created_at else None,
            data=c.model_dump(),
            platform="instagram"
        )
        comments.append(comment)
    return ExtractedEntitiesFlattened(
        comments=comments,
        accounts=accounts,
        likes=[], account_relations=[], tagged_accounts=[], media=[], posts=[]
    )


def api_v1_likes_to_entities(structure: LikersApiV1, context: ApiV1Context) -> ExtractedEntitiesFlattened:
    post_pk: Optional[str] = context.media_id
    post_url = f"p/{media_id_to_shortcode(int(post_pk))}/" if post_pk else None
    extracted_likes: list[Like] = []
    accounts: list[Account] = []
    for u in structure.users:
        accounts.append(Account(
            id_on_platform=u.pk,
            url_suffix=f"{u.username}/",
            display_name=u.full_name,
            bio=None,
            data=u.model_dump(),
            platform="instagram"
        ))
        extracted_likes.append(Like(
            id_on_platform=None,
            post_id_on_platform=post_pk,
            post_url_suffix=post_url,
            account_id_on_platform=u.pk,
            account_url_suffix=f"{u.username}/",
            data=u.model_dump(),
            platform="instagram"
        ))
    return ExtractedEntitiesFlattened(
        likes=extracted_likes,
        accounts=accounts,
        comments=[], account_relations=[], tagged_accounts=[], media=[], posts=[]
    )


def api_v1_friendships_to_entities(structure: FriendshipsApiV1, context: ApiV1Context) -> ExtractedEntitiesFlattened:
    url: Optional[str] = context.url
    follow_direction = ("followers" if url and "followers" in url
                        else ("following" if url and "following" in url else None))
    target_account_id = url.split("friendships/")[1].split("/")[0] if url else None
    extracted_account_relations: list[AccountRelation] = []
    accounts: list[Account] = []
    for u in structure.users:
        account = Account(
            url_suffix=f"{u.username}/",
            display_name=u.full_name,
            bio=None,
            id_on_platform=u.id,
            data=u.model_dump(),
            platform="instagram"
        )
        accounts.append(account)
        if follow_direction == "followers":
            relation = AccountRelation(
                follower_account_id_on_platform=u.id,
                follower_account_url_suffix=f"{u.username}/",
                followed_account_id_on_platform=target_account_id,
                relation_type='follower',
                data=None,
                platform="instagram"
            )
        else:
            relation = AccountRelation(
                follower_account_id_on_platform=target_account_id,
                followed_account_id_on_platform=u.id,
                followed_account_url_suffix=f"{u.username}/",
                relation_type='follower',
                data=None,
                platform="instagram"
            )
        extracted_account_relations.append(relation)
    return ExtractedEntitiesFlattened(
        account_relations=extracted_account_relations,
        accounts=accounts,
        comments=[], likes=[], tagged_accounts=[], media=[], posts=[]
    )


def page_to_entities(structure: PageResponse) -> ExtractedEntitiesFlattened:
    entities = ExtractedEntitiesFlattened(
        accounts=[], posts=[], media=[], comments=[], likes=[], account_relations=[], tagged_accounts=[]
    )
    if structure.posts:
        extend_flattened_entities(entities, page_posts_to_entities(structure.posts))
    if structure.highlight_reels:
        extend_flattened_entities(entities, page_highlight_reels_to_entities(structure.highlight_reels))
    if structure.stories:
        extend_flattened_entities(entities, graphql_reels_media_to_entities(structure.stories))
    if structure.stories_direct:
        extend_flattened_entities(entities, page_stories_to_entities(structure.stories_direct))
    if structure.comments and structure.posts:
        extend_flattened_entities(entities, page_comments_to_entities(structure.comments, structure.posts))
    return entities


def page_posts_to_entities(structure: MediaShortcode) -> ExtractedEntitiesFlattened:
    extracted_accounts: list[Account] = []
    extracted_posts: list[Post] = []
    extracted_media: list[Media] = []
    extracted_tagged_accounts: list[TaggedAccount] = []
    for item in structure.items:
        _username = (item.user.username if item.user else None) or (item.owner.username if item.owner else None)
        _fullname = (item.user.full_name if item.user else None) or (item.owner.full_name if item.owner else None)
        _user_id = (item.user.id if item.user else None) or (item.owner.id if item.owner else None)
        account: Account = Account(
            id_on_platform=_user_id,
            url_suffix=f"{_username}/" if _username else (f"id:{_user_id}" if _user_id else None),
            display_name=_fullname,
            bio=None,
            data=item.user.model_dump() if item.user else None,
            platform="instagram"
        )
        extracted_accounts.append(account)
        post_pk = item.pk or item.id
        post_code = item.code or (media_id_to_shortcode(int(post_pk)) if post_pk else None)
        post = Post(
            id_on_platform=item.pk or item.id,
            url_suffix=f"p/{post_code}" if post_code else None,
            account_id_on_platform=account.id_on_platform,
            account_url_suffix=account.url_suffix,
            publication_date=datetime.fromtimestamp(float(item.taken_at), timezone.utc) if item.taken_at else None,
            caption=item.caption.text if item.caption else None,
            data=item.model_dump(),
            platform="instagram"
        )
        extracted_posts.append(post)
        asset_url = (item.video_versions[0].url if item.video_versions
                     else (item.image_versions2.candidates[0].url
                           if item.image_versions2 and item.image_versions2.candidates else None))
        first_media = Media(
            id_on_platform=item.id,
            url_suffix=canonical_cdn_url(asset_url) if asset_url else None,
            post_id_on_platform=post.id_on_platform,
            post_url_suffix=post.url_suffix,
            local_url=None,
            media_type="video" if item.video_versions else "image",
            data=item.model_dump(exclude={'carousel_media'}),
            platform="instagram"
        )
        extracted_media.append(first_media)
        if item.usertags and item.usertags.in_field:
            for tag in item.usertags.in_field:
                extracted_tagged_accounts.append(TaggedAccount(
                    tagged_account_id_on_platform=tag.user.id,
                    tagged_account_url_suffix=f"{tag.user.username}/",
                    context_post_url_suffix=post.url_suffix,
                    context_media_url_suffix=first_media.url_suffix,
                    context_post_id_on_platform=post.id_on_platform,
                    context_media_id_on_platform=first_media.id_on_platform,
                    tag_x_position=tag.position[0] if tag.position else None,
                    tag_y_position=tag.position[1] if tag.position and len(tag.position) > 1 else None,
                    data=None,
                    platform="instagram"
                ))
                extracted_accounts.append(Account(
                    id_on_platform=tag.user.id,
                    url_suffix=f"{tag.user.username}/",
                    display_name=tag.user.full_name,
                    bio=None,
                    data=tag.user.model_dump(),
                    platform="instagram"
                ))
        if item.carousel_media:
            for media_item in item.carousel_media:
                url = (media_item.video_versions[0].url if media_item.video_versions else (
                    media_item.image_versions2.candidates[0].url
                    if media_item.image_versions2 and media_item.image_versions2.candidates
                    else None
                ))
                url_suffix = canonical_cdn_url(url) if url else None
                extracted_media.append(Media(
                    id_on_platform=media_item.id,
                    url_suffix=url_suffix,
                    post_id_on_platform=post.id_on_platform,
                    post_url_suffix=post.url_suffix,
                    local_url=None,
                    media_type="image" if media_item.media_type == 1 else "video",
                    data=media_item.model_dump(),
                    platform="instagram"
                ))
                if media_item.usertags and media_item.usertags.in_field:
                    for tag in media_item.usertags.in_field:
                        extracted_tagged_accounts.append(TaggedAccount(
                            tagged_account_id_on_platform=tag.user.id,
                            tagged_account_url_suffix=f"{tag.user.username}/",
                            context_post_url_suffix=post.url_suffix,
                            context_media_url_suffix=url_suffix,
                            context_post_id_on_platform=post.id_on_platform,
                            context_media_id_on_platform=media_item.id,
                            tag_x_position=tag.position[0] if tag.position else None,
                            tag_y_position=tag.position[1] if tag.position and len(tag.position) > 1 else None,
                            data=None,
                            platform="instagram"
                        ))
                        extracted_accounts.append(Account(
                            id_on_platform=tag.user.id,
                            url_suffix=f"{tag.user.username}/",
                            display_name=tag.user.full_name,
                            bio=None,
                            data=tag.user.model_dump(),
                            platform="instagram"
                        ))
    return ExtractedEntitiesFlattened(
        accounts=extracted_accounts,
        posts=extracted_posts,
        media=extracted_media,
        tagged_accounts=extracted_tagged_accounts,
        likes=[], comments=[], account_relations=[]
    )


def page_highlight_reels_to_entities(structure: HighlightsReelConnection) -> ExtractedEntitiesFlattened:
    extracted_posts: list[Post] = []
    extracted_accounts: list[Account] = []
    extracted_media: list[Media] = []
    extracted_tagged_accounts: list[TaggedAccount] = []
    highlight = structure.edges[0].node if structure.edges else None
    highlight_id = highlight.id.split(":")[-1] if highlight else None
    if not highlight:
        return ExtractedEntitiesFlattened(
            accounts=[], posts=[], media=[], comments=[], likes=[], account_relations=[],
            tagged_accounts=[]
        )
    account = Account(
        id_on_platform=highlight.user.id,
        url_suffix=f"{highlight.user.username}/",
        display_name=None,
        bio=None,
        data=highlight.user.model_dump(),
        platform="instagram"
    )
    extracted_accounts.append(account)
    for reel in highlight.items:
        post = Post(
            id_on_platform=reel.pk or reel.id,
            url_suffix=f"s/{highlight_id}/?story_media_id={reel.pk or reel.id}",
            account_id_on_platform=highlight.user.id,
            account_url_suffix=account.url_suffix,
            publication_date=datetime.fromtimestamp(reel.taken_at, timezone.utc),
            caption=reel.caption.text if reel.caption else None,
            data=reel.model_dump(),
            platform="instagram"
        )
        extracted_posts.append(post)
        reel_asset_url = (reel.video_versions[0].url if reel.video_versions
                          else (reel.image_versions2.candidates[0].url
                                if reel.image_versions2 and reel.image_versions2.candidates else None))
        extracted_media.append(Media(
            id_on_platform=reel.id,
            url_suffix=canonical_cdn_url(reel_asset_url) if reel_asset_url else None,
            post_id_on_platform=post.id_on_platform,
            post_url_suffix=post.url_suffix,
            local_url=None,
            media_type="video" if reel.video_versions else "image",
            data=reel.model_dump(),
            platform="instagram"
        ))
        if reel.story_bloks_stickers:
            for sticker in reel.story_bloks_stickers:
                extracted_tagged_accounts.append(TaggedAccount(
                    tagged_account_id_on_platform=None,
                    tagged_account_url_suffix=f"{sticker.bloks_sticker.sticker_data.ig_mention.username}/",
                    context_post_url_suffix=post.url_suffix,
                    context_media_url_suffix=None,
                    context_post_id_on_platform=post.id_on_platform,
                    context_media_id_on_platform=None,
                    data=None,
                    platform="instagram"
                ))
                extracted_accounts.append(Account(
                    id_on_platform=None,
                    url_suffix=f"{sticker.bloks_sticker.sticker_data.ig_mention.username}/",
                    display_name=sticker.bloks_sticker.sticker_data.ig_mention.full_name,
                    bio=None,
                    data=sticker.bloks_sticker.sticker_data.ig_mention.model_dump(),
                    platform="instagram"
                ))
        if reel.carousel_media:
            for media_item in reel.carousel_media:
                carousel_asset_url = (media_item.video_versions[0].url if media_item.video_versions
                                      else (media_item.image_versions2.candidates[0].url
                                            if media_item.image_versions2 and media_item.image_versions2.candidates else None))
                media_url_suffix = canonical_cdn_url(carousel_asset_url) if carousel_asset_url else None
                extracted_media.append(Media(
                    id_on_platform=media_item.id,
                    url_suffix=media_url_suffix,
                    post_id_on_platform=post.id_on_platform,
                    post_url_suffix=post.url_suffix,
                    local_url=None,
                    media_type="image" if media_item.media_type == 1 else "video",
                    data=media_item.model_dump(),
                    platform="instagram"
                ))
                if media_item.usertags and media_item.usertags.in_field:
                    for tag in media_item.usertags.in_field:
                        extracted_tagged_accounts.append(TaggedAccount(
                            tagged_account_id_on_platform=tag.user.id,
                            tagged_account_url_suffix=f"{tag.user.username}/",
                            context_post_url_suffix=post.url_suffix,
                            context_media_url_suffix=media_url_suffix,
                            context_post_id_on_platform=post.id_on_platform,
                            context_media_id_on_platform=media_item.id,
                            tag_x_position=tag.position[0] if tag.position else None,
                            tag_y_position=tag.position[1] if tag.position and len(tag.position) > 1 else None,
                            data=None,
                            platform="instagram"
                        ))
                        extracted_accounts.append(Account(
                            id_on_platform=tag.user.id,
                            url_suffix=f"{tag.user.username}/",
                            display_name=tag.user.full_name,
                            bio=None,
                            data=tag.user.model_dump(),
                            platform="instagram"
                        ))
    return ExtractedEntitiesFlattened(
        accounts=extracted_accounts,
        posts=extracted_posts,
        media=extracted_media,
        tagged_accounts=extracted_tagged_accounts,
        comments=[], likes=[], account_relations=[]
    )


def page_stories_to_entities(structure: StoriesFeed) -> ExtractedEntitiesFlattened:
    extracted_accounts: list[Account] = []
    extracted_posts: list[Post] = []
    extracted_media: list[Media] = []
    extracted_tagged_accounts: list[TaggedAccount] = []
    reels_media = structure.reels_media[0] if structure.reels_media and len(structure.reels_media) > 0 else None
    if not reels_media:
        return ExtractedEntitiesFlattened(
            accounts=[], posts=[], media=[], comments=[], likes=[], account_relations=[],
            tagged_accounts=[]
        )
    account = Account(
        id_on_platform=reels_media.user.id,
        url_suffix=f"{reels_media.user.username}/",
        display_name=None,
        bio=None,
        data=reels_media.user.model_dump(),
        platform="instagram"
    )
    extracted_accounts.append(account)
    for item in reels_media.items:
        post = Post(
            id_on_platform=item.pk or item.id,
            url_suffix=f"stories/{reels_media.user.username}/{item.pk or item.id}/",
            account_id_on_platform=reels_media.user.id,
            account_url_suffix=account.url_suffix,
            publication_date=datetime.fromtimestamp(float(item.taken_at), timezone.utc) if item.taken_at else None,
            caption=item.caption.text if item.caption else None,
            data=item.model_dump(),
            platform="instagram"
        )
        extracted_posts.append(post)
        if item.story_bloks_stickers:
            for sticker in item.story_bloks_stickers:
                extracted_tagged_accounts.append(TaggedAccount(
                    tagged_account_id_on_platform=None,
                    tagged_account_url_suffix=f"{sticker.bloks_sticker.sticker_data.ig_mention.username}/",
                    context_post_url_suffix=post.url_suffix,
                    context_media_url_suffix=None,
                    context_post_id_on_platform=post.id_on_platform,
                    context_media_id_on_platform=None,
                    data=None,
                    platform="instagram"
                ))
                extracted_accounts.append(Account(
                    id_on_platform=None,
                    url_suffix=f"{sticker.bloks_sticker.sticker_data.ig_mention.username}/",
                    display_name=sticker.bloks_sticker.sticker_data.ig_mention.full_name,
                    bio=None,
                    data=sticker.bloks_sticker.sticker_data.ig_mention.model_dump(),
                    platform="instagram"
                ))
        story_asset_url = (item.video_versions[0].url if item.video_versions
                           else (item.image_versions2.candidates[0].url
                                 if item.image_versions2 and item.image_versions2.candidates else None))
        extracted_media.append(Media(
            id_on_platform=item.id,
            url_suffix=canonical_cdn_url(story_asset_url) if story_asset_url else None,
            post_id_on_platform=post.id_on_platform,
            post_url_suffix=post.url_suffix,
            local_url=None,
            media_type="video" if item.video_versions else "image",
            data=item.model_dump(),
            platform="instagram"
        ))
        if item.carousel_media:
            for media_item in item.carousel_media:
                carousel_asset_url = (media_item.video_versions[0].url if media_item.video_versions
                                      else (media_item.image_versions2.candidates[0].url
                                            if media_item.image_versions2 and media_item.image_versions2.candidates else None))
                media_url_suffix = canonical_cdn_url(carousel_asset_url) if carousel_asset_url else None
                extracted_media.append(Media(
                    id_on_platform=media_item.id,
                    url_suffix=media_url_suffix,
                    post_id_on_platform=post.id_on_platform,
                    post_url_suffix=post.url_suffix,
                    local_url=None,
                    media_type="image" if media_item.media_type == 1 else "video",
                    data=media_item.model_dump(),
                    platform="instagram"
                ))
                if media_item.usertags and media_item.usertags.in_field:
                    for tag in media_item.usertags.in_field:
                        extracted_tagged_accounts.append(TaggedAccount(
                            tagged_account_id_on_platform=tag.user.id,
                            tagged_account_url_suffix=f"{tag.user.username}/",
                            context_post_url_suffix=post.url_suffix,
                            context_media_url_suffix=media_url_suffix,
                            context_post_id_on_platform=post.id_on_platform,
                            context_media_id_on_platform=media_item.id,
                            tag_x_position=tag.position[0] if tag.position else None,
                            tag_y_position=tag.position[1] if tag.position and len(tag.position) > 1 else None,
                            data=None,
                            platform="instagram"
                        ))
                        extracted_accounts.append(Account(
                            id_on_platform=tag.user.id,
                            url_suffix=f"{tag.user.username}/",
                            display_name=tag.user.full_name,
                            bio=None,
                            data=tag.user.model_dump(),
                            platform="instagram"
                        ))
    return ExtractedEntitiesFlattened(
        accounts=extracted_accounts,
        posts=extracted_posts,
        media=extracted_media,
        tagged_accounts=extracted_tagged_accounts,
        comments=[], likes=[], account_relations=[]
    )


def page_comments_to_entities(comments_structure: CommentsConnection,
                              post_structure: MediaShortcode) -> ExtractedEntitiesFlattened:
    extracted_comments: list[Comment] = []
    extracted_accounts: list[Account] = []
    try:
        post_item = post_structure.items[0] if post_structure.items else None
        post_pk: Optional[str] = post_item.pk if post_item else None
        post_code: Optional[str] = post_item.code if post_item else None
        post_url = f"p/{post_code or media_id_to_shortcode(int(post_pk))}/" if post_pk else None
        for e in comments_structure.edges:
            c = e.node
            account = Account(
                id_on_platform=c.user.pk if c.user else None,
                url_suffix=f"{c.user.username}/" if c.user else None,
                data=c.user.model_dump() if c.user else None,
                display_name=None, bio=None,
                platform="instagram"
            )
            extracted_accounts.append(account)
            comment = Comment(
                id_on_platform=c.pk,
                url_suffix=f"{post_url}c/{c.pk}/" if post_url else None,
                post_id_on_platform=post_pk,
                post_url_suffix=post_url,
                account_id_on_platform=account.id_on_platform,
                account_url_suffix=account.url_suffix,
                text=c.text,
                parent_comment_id_on_platform=c.parent_comment_id,
                publication_date=datetime.fromtimestamp(c.created_at) if c.created_at else None,
                data=c.model_dump(),
                platform="instagram"
            )
            extracted_comments.append(comment)
    except Exception as ex:
        print(f"Error extracting comments from page: {ex}")
    return ExtractedEntitiesFlattened(
        comments=extracted_comments,
        accounts=extracted_accounts,
        likes=[], account_relations=[], tagged_accounts=[], media=[], posts=[]
    )


def canonical_cdn_url(url: str) -> str:
    return url.split("?")[0].split("/")[-1]


def media_id_to_shortcode(media_id: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    shortcode = ''
    while media_id > 0:
        media_id, remainder = divmod(media_id, 64)
        shortcode = alphabet[remainder] + shortcode
    return shortcode


T = TypeVar("T")


def deduplicate_list_by_multiple_keys(
        entries: list[T],
        key_fields: list[Callable[[T], Optional[str]]],
        merge_function: Callable[[T, T], T] = None
) -> list[T]:
    # Filter down the set of entries such that no two entries have the same values for *any* of the key fields, unless the value is None
    unique_entries: list[T] = []
    entries_key_map: dict[tuple, int] = dict()
    for entry in entries:
        existing_copy: Optional[int] = None
        for key_index in range(len(key_fields)):
            key_field = key_fields[key_index]
            key_value = key_field(entry)
            if key_value is not None:
                key = (key_index, key_value)
                if key in entries_key_map:
                    existing_copy = entries_key_map[key]
                    break
        if existing_copy is None:
            unique_entries.append(entry)
            existing_copy = len(unique_entries) - 1
        else:
            unique_entries[existing_copy] = merge_function(unique_entries[existing_copy], entry) if merge_function else \
                unique_entries[existing_copy]
        assert existing_copy is not None
        for key_index in range(len(key_fields)):
            key_field = key_fields[key_index]
            key_value = key_field(entry)
            if key_value is not None:
                key = (key_index, key_value)
                entries_key_map[key] = existing_copy
    return unique_entries


def deduplicate_entities(entities: ExtractedEntitiesFlattened) -> ExtractedEntitiesFlattened:
    return ExtractedEntitiesFlattened(
        accounts=deduplicate_list_by_multiple_keys(
            entities.accounts,
            [
                lambda x: x.id_on_platform,
                lambda x: x.url
            ],
            reconcile_accounts
        ),
        posts=deduplicate_list_by_multiple_keys(
            entities.posts,
            [
                lambda x: x.id_on_platform,
                lambda x: x.url
            ],
            reconcile_posts
        ),
        media=deduplicate_list_by_multiple_keys(
            entities.media,
            [
                lambda x: x.id_on_platform,
                lambda x: x.url
            ],
            reconcile_media
        ),
        comments=deduplicate_list_by_multiple_keys(entities.comments, [
            lambda x: x.id_on_platform,
            lambda x: x.url
        ]),
        likes=deduplicate_list_by_multiple_keys(entities.likes, [
            lambda x: x.id_on_platform,
        ]),
        account_relations=deduplicate_list_by_multiple_keys(entities.account_relations, [
            lambda x: x.id_on_platform,
        ]),
        tagged_accounts=deduplicate_list_by_multiple_keys(entities.tagged_accounts, [
            lambda x: x.id_on_platform,
            lambda x: "_".join([
                x.tagged_account_url or "",
                x.context_post_url or "",
                x.context_media_url or ""
            ]) if x.tagged_account_url and (x.context_post_url or x.context_media_url) else None
        ])
    )


def manual_entity_extraction():
    # Provide the path to your .har file and desired output folder
    har_file = input("Input path to HAR file: ")  # Replace with your actual HAR file
    # Strip leading and trailing whitespace as well as " " or " from the input
    har_file = har_file.strip().strip('"').strip("'")
    har_path = Path(har_file)
    entities = extract_entities_from_har(
        har_path,
        video_acquisition_config=VideoAcquisitionConfig(
            download_missing=False,
            download_media_not_in_structures=False,
            download_unfetched_media=False,
            download_full_versions_of_fetched_media=False,
            download_highest_quality_assets_from_structures=False
        ),
        photo_acquisition_config=PhotoAcquisitionConfig(
            download_missing=False,
            download_media_not_in_structures=False,
            download_unfetched_media=False,
            download_highest_quality_assets_from_structures=False
        )
    )
    print(entities)


if __name__ == '__main__':
    manual_entity_extraction()
