"""Generic, platform-agnostic structure detection.

Defines the ``StructureType`` union (Instagram ∪ Threads ∪ ...) and a single
per-entry detector, ``extract_structure_from_entry``, that routes each HAR/WARC
entry to the matching platform's detector **by request host**. Host routing is
what lets a single mixed-platform HAR (Instagram *and* Threads traffic captured
in one session) be parsed without any global pivot — each entry is classified
independently.

All callers (``structures_from_har``, ``keep_only_requests_for_known_structures``,
``_scan_har_once`` and the WACZ scanner) go through this one function, so the
detection logic lives in exactly one place per platform.
"""
import json
import traceback
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

import ijson

from extractors.instagram import structures_extraction as _ig
from extractors.threads import structures_extraction as _th
from extractors.instagram.structures_extraction_graphql import GraphQLResponse
from extractors.instagram.structures_extraction_api_v1 import ApiV1Response
from extractors.instagram.structures_extraction_html import PageResponse
from extractors.threads.structures_extraction import ThreadsResponse

StructureType = Union[GraphQLResponse, ApiV1Response, PageResponse, ThreadsResponse]


def _entry_host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def extract_structure_from_entry(entry: dict) -> Optional[StructureType]:
    """Route one HAR/WARC entry to the matching platform detector by host."""
    host = _entry_host(entry["request"]["url"])
    if _ig.is_instagram_host(host):
        return _ig.extract_structure_from_entry(entry)
    if _th.is_threads_host(host):
        return _th.extract_structure_from_entry(entry)
    return None


def opened_post_structures(structures: list[StructureType]) -> list[StructureType]:
    """Narrow a structure list to the responses that only appear when a specific
    post was *opened*, as opposed to merely scrolled past in a feed.

    Instagram serves post-detail payloads from three places, none of which a
    timeline/grid/reels-tab response ever carries:

    - ``/api/v1/media/{pk}/info/``      -> ``ApiV1Response.media_info``
    - the SPA's shortcode GraphQL query -> ``GraphQLResponse.post_shortcode``
    - a ``/p/{shortcode}/`` page bootstrap -> ``PageResponse.posts``

    This matters because Instagram preloads the head of every video in a
    profile timeline, so "was fetched during the session" cannot tell an opened
    post apart from one that merely scrolled into view. The post-detail request
    can: it is issued on click and on nothing else.

    Threads has no equivalent discriminator (``ThreadsResponse`` carries one
    undifferentiated ``posts`` list), so Threads structures are never reported
    as opened. Callers must treat an empty result as "cannot determine" rather
    than "nothing was opened".

    Each match is returned as a *narrowed copy* holding only the post-detail
    field, so a caller that traverses the result never sees a bulk feed that
    happened to ride along in the same response.
    """
    opened: list[StructureType] = []
    for s in structures:
        if isinstance(s, ApiV1Response) and s.media_info:
            opened.append(ApiV1Response(context=s.context, media_info=s.media_info))
        elif isinstance(s, GraphQLResponse) and s.post_shortcode:
            opened.append(GraphQLResponse(context=s.context, post_shortcode=s.post_shortcode))
        elif isinstance(s, PageResponse) and s.posts:
            opened.append(PageResponse(
                posts=s.posts,
                comments=None,
                timelines=None,
                highlight_reels=None,
                stories=None,
                stories_direct=None,
            ))
    return opened


def structures_from_har(har_path: Path) -> list[StructureType]:
    structures: list[StructureType] = []
    with open(har_path, "rb") as f:
        for entry in ijson.items(f, "log.entries.item"):
            try:
                structure = extract_structure_from_entry(entry)
                if structure:
                    structures.append(structure)
            except Exception as e:
                print(f"Error processing entry: {e}")
                traceback.print_exc()
    return structures


def keep_only_requests_for_known_structures(har_path: Path, clean_original: bool = False):
    """Filter a HAR down to only the entries that carry a recognized structure
    (any supported platform), writing ``{stem}_filtered.har``."""
    with open(har_path, "rb") as f:
        relevant_entries = []
        for entry in ijson.items(f, "log.entries.item"):
            try:
                if extract_structure_from_entry(entry):
                    relevant_entries.append(entry)
            except Exception as e:
                print(f"Error processing entry: {e}")
                traceback.print_exc()
        filtered_har_path = har_path.with_name(har_path.stem + "_filtered.har")

    with open(har_path, "rb") as f_meta:
        with open(filtered_har_path, "w", encoding="utf-8") as f_filtered:
            har_data = {"log": dict()}
            for key, value in ijson.kvitems(f_meta, 'log'):
                if key == "entries":
                    har_data["log"]["entries"] = relevant_entries
                else:
                    har_data["log"][key] = value
            json.dump(har_data, f_filtered, indent=2, default=str)
    if clean_original:
        har_path.unlink()
        print(f"Original HAR file {har_path} removed.")


def main(har_path):
    structures = structures_from_har(har_path)
    print(f"Extracted {len(structures)} structures.")
    keep_only_requests_for_known_structures(har_path)


if __name__ == '__main__':
    har_file = input("Input path to HAR file: ")
    har_file = har_file.strip().strip('"').strip("'")
    main(Path(har_file))
