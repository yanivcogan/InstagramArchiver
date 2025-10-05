from fastapi import Request

from browsing_platform.server.services.enriched_entities import EntitiesTransformConfig, FlattenedEntitiesTransform, \
    NestedEntitiesTransform


def extract_entities_transform_config(request: Request) -> EntitiesTransformConfig:
    params = request.query_params
    config: EntitiesTransformConfig = EntitiesTransformConfig(
        flattened_entities_transform=FlattenedEntitiesTransform(
            local_files_root=params.get("lfr", None) or None,
            retain_only_media_with_local_files=params.get("mwf") == "true" if params.get("mwf") is not None else False,
        ),
        nested_entities_transform=NestedEntitiesTransform(
            retain_only_posts_with_media=params.get("pwm") == "true" if params.get("pwm") is not None else False,
            retain_only_accounts_with_posts=params.get("awp") == "true" if params.get("awp") is not None else False,
        )
    )
    return config
