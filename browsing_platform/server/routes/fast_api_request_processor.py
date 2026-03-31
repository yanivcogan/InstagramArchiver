import os

from fastapi import Request

from browsing_platform.server.services.archiving_session import ArchivingSessionTransform
from browsing_platform.server.services.enriched_entities import EntitiesTransformConfig, FlattenedEntitiesTransform, \
    NestedEntitiesTransform
from browsing_platform.server.services.permissions import parse_token_from_header
from browsing_platform.server.services.search import SearchResultTransform
from browsing_platform.server.services.sharing_manager import get_link_permissions

SERVER_HOST = os.getenv("SERVER_HOST")


def extract_entities_transform_config(request: Request) -> EntitiesTransformConfig:
    params = request.query_params
    auth_header = request.headers.get("Authorization")
    token = parse_token_from_header(auth_header)
    config: EntitiesTransformConfig = EntitiesTransformConfig(
        flattened_entities_transform=FlattenedEntitiesTransform(
            access_token=params.get("st", None) or token,
            local_files_root=params.get("lfr", None) or SERVER_HOST,
            retain_only_media_with_local_files=params.get("mwf") == "true" if params.get("mwf") is not None else False,
            strip_raw_data=params.get("srd") is None or params.get("srd") != "0",
        ),
        nested_entities_transform=NestedEntitiesTransform(
            retain_only_posts_with_media=params.get("pwm") == "true" if params.get("pwm") is not None else False,
            retain_only_accounts_with_posts=params.get("awp") == "true" if params.get("awp") is not None else False,
        )
    )
    return config


def extract_session_transform_config(request: Request) -> ArchivingSessionTransform:
    params = request.query_params
    auth_header = request.headers.get("Authorization")
    token = parse_token_from_header(auth_header)

    include_screen_recordings = True
    include_har = True
    if not token:
        share_link = request.headers.get("X-Share-Link")
        if share_link:
            share_perms = get_link_permissions(share_link)
            include_screen_recordings = share_perms.include_screen_recordings
            include_har = share_perms.include_har

    config: ArchivingSessionTransform = ArchivingSessionTransform(
        access_token=params.get("st", None) or token,
        local_files_root=params.get("lfr", None) or SERVER_HOST,
        properties_to_censor=[] if token else ["signature", "profile_name", "har_archive", "my_ip"],
        include_screen_recordings=include_screen_recordings,
        include_har=include_har,
    )
    return config


def extract_search_results_config(request: Request) -> SearchResultTransform:
    params = request.query_params
    auth_header = request.headers.get("Authorization")
    token = parse_token_from_header(auth_header)
    config: SearchResultTransform = SearchResultTransform(
        access_token=token,
        local_files_root=params.get("lfr", None) or SERVER_HOST
    )
    return config
