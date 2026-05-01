import json
import traceback
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

import db
from archive_types import t_archive_types
from entity_types import Media, Post, Account, ExtractedEntitiesFlattened
from extract_entities_utils import mime_to_media_type, url_to_page_type, normalize_url, \
    get_insta_media_url_from_post_wrap
from parse_html_summary import ParsedHTMLSummary, parse_summary_by_id


class InstagramExtractedAccountDetails(BaseModel):
    pk: Optional[str] = None
    url: Optional[str] = None
    full_name: Optional[str] = None


def insta_single_item_archive_extract_account_details(post_content: dict, metadata: dict) -> Optional[Account]:
    data_attempts = []
    username_attempts = []
    id_on_platform_attempts = []
    display_name_attempts = []
    bio_attempts = []

    # vanilla
    try:
        data = post_content["data"].get("user", None)
        data_attempts.append(data)
        username_attempts.append(data.get("username", None))
        id_on_platform_attempts.append(data.get("pk", None))
        display_name_attempts.append(data.get("full_name", None))
        bio_attempts.append(None)
    except (IndexError, KeyError):
        pass
    # temporary fix (circa March 2025)
    try:
        username_attempt_2 = metadata["username"]
    except (IndexError, KeyError):
        pass
    # yt-dlp_Instagram sessions
    try:
        username_attempts.append(metadata.get("channel", None))
        id_on_platform_attempts.append(metadata.get("uploader_id", None))
        display_name_attempts.append(metadata.get("uploader", None))
        bio_attempts.append(None)
        data_attempts.append({
            "channel": metadata.get("channel", None),
            "uploader_id": metadata.get("uploader_id", None),
            "uploader": metadata.get("uploader", None)
        })
    except (IndexError, KeyError):
        pass
    # up to date
    try:
        data = (
                metadata.get("raw_data", None) or # reels and posts
                metadata.get("post_data", None) or # posts
                metadata.get("reel_data", None) or # reels
                metadata.get("data", None) # highlights
        )
        data_attempts.append(data)
        username_attempts.append(data.get("username", None))
        id_on_platform_attempts.append(data.get("pk", None))
        display_name_attempts.append(data.get("full_name", None))
        bio_attempts.append(None)
    except (IndexError, KeyError):
        pass

    data = next((x for x in data_attempts if x is not None), None)
    username = next((x for x in username_attempts if x is not None), None)
    pk = next((x for x in id_on_platform_attempts if x is not None), None)
    full_name = next((x for x in display_name_attempts if x is not None), None)
    bio = next((x for x in bio_attempts if x is not None), None)

    if username is None and pk is None:
        return None

    account_url = f"https://www.instagram.com/{username}" if username else None

    return Account(
        id_on_platform=pk,
        url=account_url,
        display_name=full_name,
        bio=bio,
        data=data
    )


def extract_insta_post(parsed_entry: ParsedHTMLSummary) -> Optional[ExtractedEntitiesFlattened]:
    metadata = parsed_entry.metadata
    post_content = parsed_entry.structures[0]
    account = insta_single_item_archive_extract_account_details(post_content, metadata)
    if account is None:
        print("can't determine enough details about the post's uploader account, skipping post")
        return None


    # determine post metadata
    post_date = None
    post_url = None
    post_pk = None
    try:
        post_date_str = parsed_entry.metadata["timestamp"]
        post_date = datetime.strptime(post_date_str, "%Y-%m-%d %H:%M:%S%z")
    except (KeyError, ValueError):
        pass
    if post_date is None:
        try:
            post_epoch_str: str = parsed_entry.metadata["entries"][0]["epoch"]
            post_date = datetime.fromtimestamp(int(post_epoch_str))
        except (KeyError, ValueError):
            pass

    if not post_url:
        print("can't determine the post url, skipping post")
        return None

    post = Post(
        url=post_url,
        id_on_platform=post_pk,
        account_url=account.url,
        publication_date=post_date,
        caption=parsed_entry.metadata.get("title", None),
        data=post_content
    )

    # flatten first media item and extra media carousel items into a single list of media items
    media_data = [post_content]
    try:
        if isinstance(post_content["other media"], list):
            media_data.extend(post_content["other media"])
        elif isinstance(post_content["other media"], dict):
            media_data.append(post_content["other media"])
    except (IndexError, KeyError):
        pass

    # process media
    media: list[Media] = []
    for media_item in media_data:
        insta_filename = get_insta_media_url_from_post_wrap(media_item)
        media.append(Media(
            url=f"https://scontent.cdninstagram.com/v/{insta_filename}",
            post_url=post_url,
            local_url=media_item["key"],
            media_type=mime_to_media_type(media_item["type"]),
            data=media_item
        ))


    return ExtractedEntitiesFlattened(
        accounts=[account],
        posts=[post],
        media=media
    )


# def extract_insta_stories(parsed_entry: ParsedHTMLSummary) -> ExtractedEntitiesFlattened:
#     story_slides = [entry for entry in parsed_entry.structures if retain_insta_content_id(entry.get("id", ""))]
#     user = None
#     try:
#         user = parsed_entry.metadata["data"]["user"]
#     except (IndexError, KeyError):
#         pass
#     extracted_posts: list[ExtractedSinglePost] = []
#     for slide in story_slides:
#         try:
#             if user is None:
#                 user = slide.get("user", None)
#             username = user.get("username", None) if user else None
#             post_url = slide["url"]
#             post_date_str = slide["date"]
#             post_date = datetime.strptime(post_date_str, "%Y-%m-%dT%H:%M:%SZ")
#             media_type = mime_to_media_type(slide["type"])
#             insta_filename = get_insta_media_url_from_post_wrap(slide)
#             local_url = slide["key"]
#             media = Media(
#                 url=f"https://scontent.cdninstagram.com/v/{insta_filename}",
#                 post_url=post_url,
#                 local_url=local_url,
#                 media_type=media_type,
#                 data=slide
#             )
#             post = Post(
#                 url=post_url,
#                 account_url=f"https://www.instagram.com/{username}/" if username else None,
#                 publication_date=post_date,
#                 caption=parsed_entry.metadata.get("title", ""),
#                 data=slide
#             )
#             extracted_posts.append(ExtractedSinglePost(
#                 post=post,
#                 media=[media]
#             ))
#         except Exception:
#             pass
#     username = user.get("username", None) if user else None
#     account = Account(
#         url=f"https://www.instagram.com/{username}/",
#         display_name=user.get("full_name", None) if user else None,
#         bio=None,
#         data=user
#     ) if username else None
#     if account:
#         return ExtractedEntitiesFlattened(
#             accounts=[
#                 ExtractedAccount(
#                     account=account,
#                     posts=extracted_posts
#                 )
#             ]
#         )
#     else:
#         return ExtractedEntitiesFlattened(
#             orphaned_posts=extracted_posts
#         )
#
#
# def extract_insta_profile_entities(parsed_entry):
#     user = parsed_entry.metadata["data"]
#     username = user["username"]
#     user_content = [entry for entry in parsed_entry.structures if retain_insta_content_id(entry.get("id", ""))]
#     extracted_posts: list[ExtractedSinglePost] = []
#     for slide in user_content:
#         try:
#             post_url = slide["url"]
#             post_date_str = slide["date"]
#             if isinstance(post_date_str, int) or (isinstance(post_date_str, str) and post_date_str.isdigit()):
#                 post_date = datetime.fromtimestamp(int(post_date_str))
#             else:
#                 post_date = datetime.strptime(post_date_str, "%Y-%m-%dT%H:%M:%SZ")
#             media_type = mime_to_media_type(slide["type"])
#             insta_filename = get_insta_media_url_from_post_wrap(slide)
#             local_url = slide["key"]
#             media = [Media(
#                 url=f"https://scontent.cdninstagram.com/v/{insta_filename}",
#                 post_url=post_url,
#                 local_url=local_url,
#                 media_type=media_type,
#                 data=slide
#             )]
#             if "other media" in slide:
#                 for m in slide["other media"]:
#                     m_media_type = mime_to_media_type(m["type"])
#                     m_local_url = m["key"]
#                     m_filename = get_insta_media_url_from_post_wrap(m)
#                     m_media = Media(
#                         url=f"https://scontent.cdninstagram.com/v/{m_filename}",
#                         post_url=post_url,
#                         local_url=m_local_url,
#                         media_type=m_media_type,
#                         data=m
#                     )
#                     media.append(m_media)
#             post = Post(
#                 url=post_url,
#                 account_url=f"https://www.instagram.com/{username}/" if username else None,
#                 publication_date=post_date,
#                 caption=parsed_entry.metadata.get("title", ""),
#                 data=slide
#             )
#             extracted_posts.append(ExtractedSinglePost(
#                 post=post,
#                 media=media
#             ))
#         except Exception:
#             pass
#     account = Account(
#         url=f"https://www.instagram.com/{username}/",
#         display_name=user.get("full_name", None),
#         bio=user.get("biography", None),
#         data=user if user else None
#     )
#     return ExtractedEntitiesFlattened(
#         accounts=[
#             ExtractedAccount(
#                 account=account,
#                 posts=extracted_posts
#             )
#         ]
#     )


# def extract_tweet_entities(parsed_entry: ParsedHTMLSummary) -> ExtractedEntities:
#     tweet_url = parsed_entry.metadata["url"]
#     username = tweet_url.split(".com/")[1].split("/")[0]
#     user_data = None
#     try:
#         twitter_full_response_json = parsed_entry.metadata.get("content")
#         twitter_full_response = json.loads(twitter_full_response_json)
#         tweet_url = parsed_entry.metadata["url"].split("?")[0].replace("https://twitter.com/", "https://x.com/")
#         user_data = twitter_full_response["user"]
#         tweet_data = twitter_full_response["tweet"]
#     except Exception:
#         pass
#     media = []
#     for e in parsed_entry.structures:
#         if "src" not in e:
#             continue
#         media.append(Media(
#             url=e["src"],
#             post_url=tweet_url,
#             local_url=e["key"],
#             media_type=mime_to_media_type(e["type"]),
#             data=e
#         ))
#     account_url = f"https://x.com/{username}"
#     post_date_str = parsed_entry.metadata["timestamp"].split("+")[0]
#     post_date = datetime.strptime(post_date_str, "%Y-%m-%d %H:%M:%S")
#     post = Post(
#         url=tweet_url,
#         account_url=account_url,
#         publication_date=post_date,
#         caption=parsed_entry.metadata["title"],
#         data=parsed_entry.metadata,
#     )
#     display_name = user_data["name"] if user_data else parsed_entry.metadata.get("author", None)
#     bio = user_data["description"] if user_data else None
#     account = Account(
#         url=account_url,
#         display_name=display_name,
#         bio=bio,
#         data=user_data
#     )
#     return ExtractedEntities(
#         accounts=[
#             ExtractedAccount(
#                 account=account,
#                 posts=[
#                     ExtractedSinglePost(
#                         post=post,
#                         media=media
#                     )
#                 ]
#             )
#         ]
#     )


# def extract_tiktok_video_entities(parsed_entry: ParsedHTMLSummary) -> ExtractedEntities:
#     archived_url = parsed_entry.metadata["url"]
#     user_name = get_tiktok_username_from_url(archived_url)
#     post_url = get_canonical_tiktok_video_url(archived_url)
#     account_url = f"https://www.tiktok.com/@{user_name}" if user_name else None
#     account_display_name = parsed_entry.metadata.get("channel", None)
#     video = parsed_entry.structures[0]
#     if "original_url" not in video:
#         print("only individual TikTok videos are supported")
#         return ExtractedEntities(accounts=[], orphaned_posts=[])
#     local_url = video["key"]
#     caption = video.get("caption", None)
#     post_date_str = video["metadata"]["File Modification Date/Time"]
#     post_date = datetime.strptime(post_date_str, "%Y:%m:%d %H:%M:%S%z")
#     media = Media(
#         url=post_url,
#         post_url=post_url,
#         local_url=local_url,
#         media_type=mime_to_media_type(video["type"]),
#         data=video
#     )
#     post = Post(
#         url=post_url,
#         account_url=account_url,
#         publication_date=post_date,
#         caption=caption,
#         data=video
#     )
#     account = Account(
#         url=account_url,
#         display_name=account_display_name,
#         bio=None,
#         data=None
#     ) if account_url else None
#     if account:
#         return ExtractedEntities(
#             accounts=[
#                 ExtractedAccount(
#                     account=account,
#                     posts=[
#                         ExtractedSinglePost(
#                             post=post,
#                             media=[media]
#                         )
#                     ]
#                 )
#             ]
#         )
#     else:
#         return ExtractedEntities(
#             orphaned_posts=[
#                 ExtractedSinglePost(
#                     post=post,
#                     media=[media]
#                 )
#             ]
#         )


# def extract_youtube_video_entities(parsed_entry):
#     video_details = parsed_entry.structures[0]
#     post_url = video_details["original_url"]
#     media_url = post_url
#     post_title = video_details.get("fulltitle", "")
#     post_description = video_details.get("description", "")
#     post_upload_date_str = video_details.get("upload_date", None)
#     post_upload_date = datetime.strptime(post_upload_date_str, "%Y%m%d") if post_upload_date_str else None
#     if post_upload_date is None:
#         post_upload_date_str = parsed_entry.metadata.get("timestamp", None)
#         post_upload_date = datetime.strptime(post_upload_date_str,
#                                              "%Y-%m-%d %H:%M:%SZ") if post_upload_date_str else None
#     channel_url = parsed_entry.metadata.get("uploader_url", None)
#     channel_title = parsed_entry.metadata.get("channel", parsed_entry.metadata.get("uploader", None))
#     media = Media(
#         url=media_url,
#         post_url=post_url,
#         local_url=video_details.get("key", None),
#         media_type="video",
#         data=video_details
#     )
#     post = Post(
#         url=post_url,
#         account_url=channel_url,
#         publication_date=post_upload_date,
#         caption=f"{post_title} ({post_description})" if post_description else post_title,
#         data=video_details
#     )
#     account = Account(
#         url=channel_url,
#         display_name=channel_title,
#         bio=None,
#         data=parsed_entry.metadata
#     ) if channel_url else None
#     if account:
#         return ExtractedEntities(
#             accounts=[
#                 ExtractedAccount(
#                     account=account,
#                     posts=[
#                         ExtractedSinglePost(
#                             post=post,
#                             media=[media]
#                         )
#                     ]
#                 )
#             ]
#         )
#     else:
#         return ExtractedEntities(
#             orphaned_posts=[
#                 ExtractedSinglePost(
#                     post=post,
#                     media=[media]
#                 )
#             ]
#         )
#
#
def extract_entities_based_on_archive_type(
        page_type: t_archive_types,
        parsed_entry: ParsedHTMLSummary
) -> ExtractedEntitiesFlattened:
    if page_type == "insta post" or page_type == "insta reel":
        return extract_insta_post(parsed_entry)
    # if page_type == "insta stories" or page_type == "insta highlights":
    #     return extract_insta_stories(parsed_entry)
    # if page_type == "insta profile":
    #     return extract_insta_profile_entities(parsed_entry)
    # if page_type == "tweet":
    #     return extract_tweet_entities(parsed_entry)
    # if page_type == "tiktok video":
    #     return extract_tiktok_video_entities(parsed_entry)
    # if page_type == "youtube video":
    #     return extract_youtube_video_entities(parsed_entry)

    raise ValueError(f"Unsupported archive type: {page_type}")


def normalize_extracted_entities(entities: ExtractedEntitiesFlattened):
    for account in entities.accounts:
        account.url = normalize_url(account.url)
    for post in entities.posts:
        post.url = normalize_url(post.url)
        post.account_url = normalize_url(post.account_url)
    for media in entities.media:
        media.url = normalize_url(media.url)
        media.post_url = normalize_url(media.post_url)
    return entities


def extract_entities_from_parsed_summary(
        url: str,
        parsed_entry: ParsedHTMLSummary,
        notes: str
) -> ExtractedEntitiesFlattened:
    page_type = url_to_page_type(url)
    entities = extract_entities_based_on_archive_type(page_type, parsed_entry)
    entities = normalize_extracted_entities(entities)
    return entities


def test_entity_extraction_by_id(entry_id: int, retry_flag: bool = False):
    entry = db.execute_query(
        """
        SELECT id,
               archived_url,
               archive_location,
               structures,
               metadata,
               notes
        FROM archive_session
        WHERE id = %(entry_id)s
        """,
        {
            "entry_id": entry_id
        },
        return_type="single_row"
    )
    if entry is None:
        print("Entry not found for id", entry_id)
        return
    try:
        print("Extracting entities for entry", entry_id)
        if entry['structures'] is None and entry['metadata'] is None:
            if not retry_flag:
                print("item not parsed yet, parsing and re-running extractor")
                parse_summary_by_id(entry_id)
                test_entity_extraction_by_id(entry_id)
                return
            else:
                print("entity extraction failure: even after attempting to parse the item, no parsing results are available.")
                return
        structures = json.loads(entry['structures'])
        metadata = json.loads(entry['metadata'])
        parsed_summary = ParsedHTMLSummary(metadata=metadata, structures=structures)
        entities = extract_entities_from_parsed_summary(entry['archived_url'], parsed_summary, entry['notes'])
        print(entities)
    except:
        traceback.print_exc()


def get_entry_id_from_aa_id(aa_id: str):
    aa_id = f"AA_YTMB{aa_id}" if not aa_id.startswith("AA_") else aa_id
    entry = db.execute_query(
        """
        SELECT id
        FROM archive_session
        WHERE external_id = %(external_id)s
        """,
        {
            "external_id": aa_id
        },
        return_type="single_row"
    )
    return entry["id"]


if __name__ == "__main__":
    # id_to_extract = 29747 or int(input("specify id for extraction: ").strip())
    id_to_extract = get_entry_id_from_aa_id(input("specify AA id: "))
    test_entity_extraction_by_id(id_to_extract)
