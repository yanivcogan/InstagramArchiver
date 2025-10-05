import {ExtractedEntitiesNested} from "../../types/entities";
import server from "../../services/server";

interface FlattenedEntitiesTransform {
    local_files_root?: string | null;
    retain_only_media_with_local_files?: boolean;
}

interface NestedEntitiesTransform {
    retain_only_posts_with_media?: boolean;
    retain_only_accounts_with_posts?: boolean;
}

interface EntitiesTransformConfig {
    flattened_entities_transform?: FlattenedEntitiesTransform | null;
    nested_entities_transform?: NestedEntitiesTransform | null;
}

const entitiesTransformConfigToQueryParams = (config: EntitiesTransformConfig): string => {
    const params = new URLSearchParams();
    if (config.flattened_entities_transform) {
        if (config.flattened_entities_transform.local_files_root !== undefined) {
            params.append("lfr", config.flattened_entities_transform.local_files_root || "");
        }
        if (config.flattened_entities_transform.retain_only_media_with_local_files !== undefined) {
            params.append("mwf", String(config.flattened_entities_transform.retain_only_media_with_local_files));
        }
    }
    if (config.nested_entities_transform) {
        if (config.nested_entities_transform.retain_only_posts_with_media !== undefined) {
            params.append("pwm", String(config.nested_entities_transform.retain_only_posts_with_media));
        }
        if (config.nested_entities_transform.retain_only_accounts_with_posts !== undefined) {
            params.append("awp", String(config.nested_entities_transform.retain_only_accounts_with_posts));
        }
    }
    return params.toString();
}

export const fetchAccount = async (accountId: number, config: EntitiesTransformConfig): Promise<ExtractedEntitiesNested> => {
    return await server.get("account/" + accountId + "/?" + entitiesTransformConfigToQueryParams(config));
}