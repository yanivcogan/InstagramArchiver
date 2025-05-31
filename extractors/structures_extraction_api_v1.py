from typing import List

from extractors.models import InstagramPost
from extractors.models_har import HarRequest


def extract_data_from_api_v1_entry(api_data: dict, req: HarRequest) -> List[InstagramPost]:
    supported_endpoints = [
        "/likers/",
        "/comments/",
        "/info/",
        "/friendships/"
    ]