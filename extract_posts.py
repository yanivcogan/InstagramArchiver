import json
from datetime import datetime

from pydantic import BaseModel


class Post(BaseModel):
    id: str
    username: str
    date: datetime
    description: str
    videos: list[str] = []
    photos: list[str] = []


def extract_post_media_ids(graphql_response):
    try:
        children = graphql_response['data']['shortcode_media']['edge_sidecar_to_children']['edges']
        return [edge['node']['id'] for edge in children]
    except KeyError:
        # Single-item post
        return [graphql_response['data']['shortcode_media']['id']]



def extract_posts(har_path:str) -> list[Post]:
    """Extracts video segment data from the HAR file."""
    with open(har_path, 'rb') as file:  # Open the file in binary mode
        har_data = json.load(file)
    post_graphqls = []
    for entry in har_data["log"]["entries"]:
        url = entry["request"]["url"]
        if "graphql/query" in url:
            try:
                response_text = entry["response"]["content"].get("text", "")
                if '"shortcode_media"' in response_text:
                    post_graphqls.append(json.loads(response_text))
            except Exception as e:
                print(f"Error parsing GraphQL response: {e}")
                continue
    posts = {}
    for post_data in post_graphqls:
        media_ids = extract_post_media_ids(post_data)
        post_id = post_data['data']['shortcode_media']['id']
        posts[post_id] = media_ids
    return []


def main(har_path):
    posts = extract_posts(har_path)


if __name__ == '__main__':
    # Provide the path to your .har file and desired output folder
    har_file = input("Input path to HAR file")  # Replace with your actual HAR file

    main(har_file)