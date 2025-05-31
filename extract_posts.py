import json
from bs4 import BeautifulSoup
from typing import List, Optional, Literal
from models import InstagramPost, PostComment  # assuming you've defined the models above in models.py


supported_entities = Literal["highlight", "story", "reel", "post", "profile"]


def infer_post_type_from_url(url: str) -> Optional[supported_entities]:
    if "instagram.com" not in url:
        return None
    if "/stories/highlights/" in url:
        return "highlight"
    elif "/stories/" in url:
        return "story"
    elif "/reel/" in url:
        return "reel"
    elif "/p/" in url:
        return "post"
    return "profile"


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


def extract_data_from_html_response(html: str) -> Optional[InstagramPost]:
    soup = BeautifulSoup(html, "html.parser")
    posts = None
    comments = None

    for script in soup.find_all("script", {"type": "application/json"}):
        if not script.string:
            continue
        try:
            json_data = json.loads(script.string)

            post_blobs = find_json_by_keyword(json_data, "xdt_api__v1__media__shortcode__web_info")
            comment_blobs = find_json_by_keyword(json_data, "xdt_api__v1__media__media_id__comments__connection")

            for post_data in post_blobs:
                for item in post_data.get("items", []):
                    post = InstagramPost(**item)

            for comment_data in comment_blobs:
                comment_edges = comment_data.get("edges", [])
                comments =[PostComment(**ce["node"]) for ce in comment_edges if "node" in ce]

        except Exception as e:
            print("Failed to parse post from HTML:", e)
            continue
    return posts


def extract_data_from_graphql_entry(graphql_data: dict) -> List[InstagramPost]:
    supported_x_fb_friendly_name_headers = [
        "PolarisProfilePostsTabContentQuery_connection",
        "PolarisProfileSuggestedUsersWithPreloadableQuery",
        "PolarisStoriesV3HighlightsPageQuery",
        "PolarisStoriesV3ReelPageStandaloneQuery"
    ]


def extract_all_posts_from_har(har_path: str) -> List[InstagramPost]:
    posts = []
    with open(har_path, "r", encoding="utf-8") as f:
        har = json.load(f)

    entries = har["log"]["entries"]

    graphql_entries = [e for e in entries if "graphql/query" in e["request"]["url"]]

    html_entries = [
        e for e in entries
        if e.get("response", {}).get("content", {}).get("mimeType", "").startswith("text/html")
    ]
    for entry in html_entries:
        try:
            html_text = entry.get("response", {}).get("content", {}).get("text")
            if not html_text:
                continue
            post = extract_data_from_html_response(html_text)
            if post:
                posts.append(post)
        except Exception:
            pass

    return posts



def main(har_path):
    posts = extract_all_posts_from_har(har_path)
    print(f"Extracted {len(posts)} posts.")


if __name__ == '__main__':
    # Provide the path to your .har file and desired output folder
    har_file = 'C:/Users/yaniv/Documents/projects/InstagramArchiver/archives/fllf_20250530_135307/archive.har' #input("Input path to HAR file")  # Replace with your actual HAR file

    main(har_file)