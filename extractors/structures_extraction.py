import json
import traceback
from pathlib import Path
from typing import List, Union
import ijson

from extractors.structures_extraction_api_v1 import extract_data_from_api_v1_entry, ApiV1Response
from extractors.structures_extraction_graphql import extract_data_from_graphql_entry, GraphQLResponse
from extractors.structures_extraction_html import extract_data_from_html_entry, Page
from extractors.models_har import HarRequest

StructureType = Union[GraphQLResponse, ApiV1Response, Page]


def structures_from_har(har_path: Path) -> list[StructureType]:
    structures = []
    with open(har_path, "rb") as f:
        entries = ijson.items(f, "log.entries.item")
        for entry in entries:
            try:
                # GraphQL
                if "graphql/query" in entry["request"]["url"]:
                    res_json = entry["response"]["content"].get("text")
                    if not res_json:
                        continue
                    structure = extract_data_from_graphql_entry(json.loads(res_json), HarRequest(**entry["request"]))
                    if structure:
                        structures.append(structure)
                # API v1
                elif "instagram.com/api/v1/media/" in entry["request"]["url"]:
                    res_json = entry["response"]["content"].get("text")
                    if not res_json:
                        continue
                    structure = extract_data_from_api_v1_entry(json.loads(res_json), HarRequest(**entry["request"]))
                    if structure:
                        structures.append(structure)
                # HTML
                elif entry["response"]["content"].get("mimeType", "").startswith("text/html"):
                    html_text = entry["response"]["content"].get("text")
                    if not html_text:
                        continue
                    structure = extract_data_from_html_entry(html_text, HarRequest(**entry["request"]))
                    if structure:
                        structures.append(structure)
            except Exception as e:
                print(f"Error processing entry: {e}")
                traceback.print_exc()
                pass
    return structures



def main(har_path):
    structures = structures_from_har(har_path)
    print(f"Extracted {len(structures)} posts.")


if __name__ == '__main__':
    # Provide the path to your .har file and desired output folder
    har_file = input("Input path to HAR file")  # Replace with your actual HAR file

    main(har_file)