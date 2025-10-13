import {IArchiveSession, IArchiveSessionWithEntities, IExtractedEntitiesNested} from "../../types/entities";
import server from "../../services/server";
import React from "react";

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

export const fetchAccount = async (accountId: number, config: EntitiesTransformConfig): Promise<IExtractedEntitiesNested> => {
    return await server.get("account/" + accountId + "/?" + entitiesTransformConfigToQueryParams(config));
}

export const fetchPost = async (postId: number, config: EntitiesTransformConfig): Promise<IExtractedEntitiesNested> => {
    return await server.get("post/" + postId + "/?" + entitiesTransformConfigToQueryParams(config));
}

export const fetchMedia = async (mediaId: number, config: EntitiesTransformConfig): Promise<IExtractedEntitiesNested> => {
    return await server.get("media/" + mediaId + "/?" + entitiesTransformConfigToQueryParams(config));
}

export const fetchArchivingSession = async (archivingSessionId: number, config: EntitiesTransformConfig): Promise<IArchiveSessionWithEntities> => {
    return await server.get("archiving_session/" + archivingSessionId + "/?" + entitiesTransformConfigToQueryParams(config));
}

export const fetchArchivingSessionsAccount = async (accountId: number): Promise<IArchiveSession[]> => {
    return await server.get("archiving_session/account/" + accountId);
}

export const fetchArchivingSessionsPost = async (postId: number): Promise<IArchiveSession[]> => {
    return await server.get("archiving_session/post/" + postId);
}

export const fetchArchivingSessionsMedia = async (mediaId: number): Promise<IArchiveSession[]> => {
    return await server.get("archiving_session/media/" + mediaId);
}

export const SEARCH_MODES: readonly {key: string, label: string}[] = [
    {key: 'media', label: 'Media'},
    {key: 'posts', label: 'Posts'},
    {key: 'accounts', label: 'Accounts'},
    {key: 'archive_sessions', label: 'Archive Sessions'},
    {key: 'all', label: 'All'},
] as const;

export type T_Search_Mode = typeof SEARCH_MODES[number]['key'];

export interface ISearchQuery {
    search_term: string;
    search_mode: T_Search_Mode;
    page_number: number;
    page_size: number;
}

export interface SearchResult {
    page: string,
    id: number,
    title: string
}

export const searchData = async (
    query: ISearchQuery,
): Promise<SearchResult[]> => {
    return await server.post("search/", query);
}