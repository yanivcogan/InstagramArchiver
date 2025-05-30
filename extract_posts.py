import json
import re
from bs4 import BeautifulSoup
from typing import List
from pathlib import Path
from models import Post, Comment  # assuming you've defined the models above in models.py


def merge_posts(existing: Post, new: Post) -> Post:
    return Post(
        username=existing.username or new.username,
        user_id=existing.user_id or new.user_id,
        post_id=existing.post_id,
        caption=existing.caption or new.caption,
        media_urls=list(set(existing.media_urls + new.media_urls)),
        timestamp=existing.timestamp or new.timestamp,
        comments=existing.comments + new.comments,
        mentions=list(set(existing.mentions + new.mentions)),
        type=new.type if new.type != "post" else existing.type
    )

def infer_post_type_from_url(url: str) -> str:
    if "/stories/" in url:
        return "story"
    elif "/reel/" in url:
        return "reel"
    elif "/highlights/" in url:
        return "highlight"
    return "post"


def extract_posts_from_graphql_entries(entries: List[dict]) -> List[Post]:
    posts = []
    for entry in entries:
        try:
            response_text = entry.get("response", {}).get("content", {}).get("text")
            if not response_text:
                continue
            data = json.loads(response_text)
            content = data.get("data", {})
            for key, value in content.items():
                if "edges" in value:
                    for edge in value["edges"]:
                        node = edge.get("node", {})
                        media = node.get("media") or node
                        if not media:
                            continue

                        user = media.get("user") or {}
                        username = user.get("username", "unknown_user")
                        user_id = user.get("id", "unknown_id")
                        post_id = media.get("id", "unknown_post_id")
                        caption = (
                            media.get("caption", {}).get("text")
                            if isinstance(media.get("caption"), dict)
                            else media.get("caption")
                        )
                        timestamp = media.get("taken_at_timestamp") or media.get("taken_at")

                        media_urls = []
                        if "image_versions2" in media:
                            media_urls = [c.get("url") for c in media["image_versions2"].get("candidates", []) if "url" in c]
                        elif "display_url" in media:
                            media_urls = [media["display_url"]]
                        elif "media_url" in media:
                            media_urls = [media["media_url"]]

                        mentions = []

                        post = Post(
                            username=username,
                            user_id=user_id,
                            post_id=post_id,
                            caption=caption,
                            media_urls=media_urls,
                            timestamp=timestamp,
                            comments=[],  # GraphQL entries might not include comments here
                            mentions=mentions,
                        )
                        posts.append(post)
        except Exception as e:
            print(f"Error processing GraphQL entry: {e}")
    return posts


def find_json_by_keyword(data: dict, keyword: str) -> List[dict]:
    matches = []

    def search(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if keyword in k and isinstance(v, dict):
                    matches.append(v)
                search(v)
        elif isinstance(obj, list):
            for item in obj:
                search(item)

    search(data)
    return matches




def extract_posts_from_html_response(html: str) -> List[Post]:
    soup = BeautifulSoup(html, "html.parser")
    posts = []

    for script in soup.find_all("script", {"type": "application/json"}):
        if not script.string:
            continue
        try:
            json_data = json.loads(script.string)

            post_blobs = find_json_by_keyword(json_data, "xdt_api__v1__media__shortcode__web_info")
            comment_blobs = find_json_by_keyword(json_data, "xdt_api__v1__media__media_id__comments__connection")

            for post_data in post_blobs:
                for item in post_data.get("items", []):
                    post_id = item.get("id")
                    user = item.get("user", {})
                    username = user.get("username", "unknown_user")
                    user_id = user.get("id", "unknown_id")

                    caption_data = item.get("caption", {})
                    caption = caption_data.get("text")
                    timestamp = item.get("taken_at")

                    media_urls = []
                    if "image_versions2" in item:
                        media_urls = [c.get("url") for c in item["image_versions2"].get("candidates", [])]
                    elif "display_url" in item:
                        media_urls = [item["display_url"]]

                    mentions = extract_mentions_from_text(caption or "")

                    # Try matching comment data via post ID
                    raw_comments = []
                    for comment_blob in comment_blobs:
                        comment_items = comment_blob.get("edges", [])
                        for comment in comment_items:
                            node = comment.get("node")
                            if node:
                                raw_comments.append(node)

                    comments = []
                    for c in raw_comments:
                        comments.append(Comment(
                            username=c.get("user", {}).get("username", "unknown"),
                            user_id=c.get("user", {}).get("id"),
                            text=c.get("text", ""),
                            timestamp=c.get("created_at"),
                        ))
                        mentions.extend(extract_mentions_from_text(c.get("text", "")))

                    post = Post(
                        username=username,
                        user_id=user_id,
                        post_id=post_id,
                        caption=caption,
                        media_urls=media_urls,
                        timestamp=timestamp,
                        comments=comments,
                        mentions=list(set(mentions))
                    )
                    posts.append(post)

        except Exception as e:
            print("Failed to parse post from HTML:", e)
            continue

    return posts



def parse_shared_post_data(data: dict) -> List[Post]:
    posts = []
    try:
        media = (
            data["entry_data"]
            .get("PostPage", [{}])[0]
            .get("graphql", {})
            .get("shortcode_media", {})
        )
        if not media:
            return []

        user = media.get("owner", {})
        username = user.get("username", "unknown_user")
        user_id = user.get("id", "unknown_id")
        post_id = media.get("id", "unknown_post_id")
        timestamp = media.get("taken_at_timestamp")

        # Caption
        caption_node = media.get("edge_media_to_caption", {}).get("edges", [])
        caption = caption_node[0]["node"]["text"] if caption_node else None

        # Media
        media_urls = []
        if "edge_sidecar_to_children" in media:
            for node in media["edge_sidecar_to_children"]["edges"]:
                media_urls.append(node["node"]["display_url"])
        elif "display_url" in media:
            media_urls = [media["display_url"]]

        # Comments
        comment_data = media.get("edge_media_to_parent_comment", {}).get("edges", [])
        comments = []
        for c in comment_data:
            comment_node = c["node"]
            comments.append(
                Comment(
                    username=comment_node.get("owner", {}).get("username"),
                    user_id=comment_node.get("owner", {}).get("id"),
                    text=comment_node.get("text"),
                    timestamp=comment_node.get("created_at"),
                )
            )

        # Mentions
        all_text = caption or "" + " ".join(c.text for c in comments)
        mentions = []

        posts.append(Post(
            username=username,
            user_id=user_id,
            post_id=post_id,
            caption=caption,
            media_urls=media_urls,
            timestamp=timestamp,
            comments=comments,
            mentions=mentions
        ))
    except Exception as e:
        print("Error parsing shared data from HTML:", e)

    return posts


def extract_all_posts_from_har(har_path: str) -> List[Post]:
    with open(har_path, "r", encoding="utf-8") as f:
        har = json.load(f)

    entries = har["log"]["entries"]
    graphql_entries = [e for e in entries if "graphql/query" in e["request"]["url"]]
    html_entries = [
        e for e in entries
        if e.get("response", {}).get("content", {}).get("mimeType", "").startswith("text/html")
    ]

    graphql_posts = extract_posts_from_graphql_entries(graphql_entries)
    html_posts = []

    for entry in html_entries:
        html_text = entry.get("response", {}).get("content", {}).get("text")
        if not html_text:
            continue

        posts = extract_posts_from_html_response(html_text)
        # infer post type from the URL
        url = entry.get("request", {}).get("url", "")
        post_type = infer_post_type_from_url(url)
        for post in posts:
            post.type = post_type
        html_posts.extend(posts)

    all_posts: dict[str, Post] = {}

    for post in graphql_posts + html_posts:
        key = post.post_id or (post.media_urls[0] if post.media_urls else None)
        if not key:
            continue
        if key in all_posts:
            all_posts[key] = merge_posts(all_posts[key], post)
        else:
            all_posts[key] = post

    return list(all_posts.values())



def main(har_path):
    posts = extract_all_posts_from_har(har_path)
    print(f"Extracted {len(posts)} posts.")


if __name__ == '__main__':
    # Provide the path to your .har file and desired output folder
    har_file = 'C:/Users/yaniv/Documents/projects/InstagramArchiver/archives/fllf_20250530_135307/archive.har' #input("Input path to HAR file")  # Replace with your actual HAR file

    main(har_file)