import json
from typing import List

from extractors.structures_extraction_api_v1 import extract_data_from_api_v1_entry
from extractors.structures_extraction_html import extract_data_from_html_entry
from models import InstagramPost
from models_har import HarFile


def extract_all_posts_from_har(har_path: str) -> List[InstagramPost]:
    structures = []
    with open(har_path, "r", encoding="utf-8") as f:
        har_dict = json.load(f)
        har = HarFile(**har_dict)

    entries = har.log.entries

    graphql_entries = [e for e in entries if "graphql/query" in e.request.url]
    for entry in graphql_entries:
        try:
            res_json = entry.response.content.text
            if not res_json:
                continue
            structure = extract_data_from_api_v1_entry(json.loads(res_json), entry.request)
            if structure:
                structures.append(structure)
        except Exception:
            pass

    api_v1_entries = [e for e in entries if "instagram.com/api/v1/media/" in e.request.url]
    for entry in api_v1_entries:
        try:
            res_json = entry.response.content.text
            if not res_json:
                continue
            structure = extract_data_from_api_v1_entry(json.loads(res_json), entry.request)
            if structure:
                structures.append(structure)
        except Exception:
            pass

    html_entries = [e for e in entries if e.response.content.mimeType.startswith("text/html")]
    for entry in html_entries:
        try:
            html_text = entry.response.content.text
            if not html_text:
                continue
            structure = extract_data_from_html_entry(html_text, entry.request)
            if structure:
                structures.append(structure)
        except Exception:
            pass

    return structures



def main(har_path):
    posts = extract_all_posts_from_har(har_path)
    print(f"Extracted {len(posts)} posts.")


if __name__ == '__main__':
    # Provide the path to your .har file and desired output folder
    har_file = '/archives/fllf_20250530_135307/archive.har'  #input("Input path to HAR file")  # Replace with your actual HAR file

    main(har_file)