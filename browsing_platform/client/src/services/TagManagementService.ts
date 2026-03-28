import server, {HTTP_METHODS} from "./server";
import {ITagDetail, ITagHierarchyEntry, ITagType, ITagUsage, ITagWithType} from "../types/tags";

const BASE = "tag-management";

export const fetchQuickAccessTags = async (): Promise<ITagWithType[]> =>
    server.get(`${BASE}/quick-access/`);

/* Tag Types */
export const fetchTagTypes = async (): Promise<ITagType[]> =>
    server.get(`${BASE}/types/`);

export const createTagType = async (body: Omit<ITagType, "id">): Promise<ITagType> =>
    server.post(`${BASE}/types/`, body);

export const updateTagType = async (id: number, body: Omit<ITagType, "id">): Promise<ITagType> =>
    server.post(`${BASE}/types/${id}`, body, HTTP_METHODS.put);

export const deleteTagType = async (id: number): Promise<void> =>
    server.post(`${BASE}/types/${id}`, {}, HTTP_METHODS.delete);

/* Tags */
export const fetchTags = async (params?: {
    tag_type_id?: number;
    q?: string;
    page?: number;
    page_size?: number;
}): Promise<ITagDetail[]> => {
    const qs = new URLSearchParams();
    if (params?.tag_type_id != null) qs.append("tag_type_id", String(params.tag_type_id));
    if (params?.q) qs.append("q", params.q);
    if (params?.page) qs.append("page", String(params.page));
    if (params?.page_size) qs.append("page_size", String(params.page_size));
    return server.get(`${BASE}/tags/?${qs.toString()}`);
};

export const createTag = async (body: Omit<ITagDetail, "id" | "tag_type_name">): Promise<ITagDetail> =>
    server.post(`${BASE}/tags/`, body);

export const updateTag = async (id: number, body: Omit<ITagDetail, "id" | "tag_type_name">): Promise<ITagDetail> =>
    server.post(`${BASE}/tags/${id}`, body, HTTP_METHODS.put);

export const deleteTag = async (id: number): Promise<void> =>
    server.post(`${BASE}/tags/${id}`, {}, HTTP_METHODS.delete);

export const fetchTagUsage = async (id: number): Promise<ITagUsage> =>
    server.get(`${BASE}/tags/${id}/usage/`);

export const fetchTagChildren = async (id: number): Promise<ITagHierarchyEntry[]> =>
    server.get(`${BASE}/tags/${id}/children/`);

export const fetchTagParents = async (id: number): Promise<ITagHierarchyEntry[]> =>
    server.get(`${BASE}/tags/${id}/parents/`);

/* Hierarchy */
export const addHierarchy = async (body: ITagHierarchyEntry): Promise<ITagHierarchyEntry> =>
    server.post(`${BASE}/hierarchy/`, body);

export const removeHierarchy = async (super_tag_id: number, sub_tag_id: number): Promise<void> =>
    server.post(`${BASE}/hierarchy/`, {super_tag_id, sub_tag_id}, HTTP_METHODS.delete);

export const updateHierarchyNotes = async (
    super_tag_id: number,
    sub_tag_id: number,
    notes: string | null
): Promise<void> =>
    server.post(`${BASE}/hierarchy/`, {super_tag_id, sub_tag_id, notes}, HTTP_METHODS.patch);
