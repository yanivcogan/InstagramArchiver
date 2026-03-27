interface ITag {
    id: number;
    create_date: string;
    update_date: string;
    name: string;
    description?: string | null;
    tag_type_id?: number | null;
}

export interface ITagWithType extends ITag {
    tag_type_name: string | null;
    tag_type_description: string | null;
    tag_type_notes: string | null;
    assignment_notes?: string | null;
    tag_type_entity_affinity?: string[] | null;
}

export interface ITagType {
    id?: number;
    name: string;
    description?: string | null;
    notes?: string | null;
    entity_affinity?: string[] | null;
}

export interface ITagDetail {
    id?: number;
    name: string;
    description?: string | null;
    tag_type_id?: number | null;
    tag_type_name?: string | null;
    quick_access?: boolean;
}

export interface ITagHierarchyEntry {
    super_tag_id: number;
    sub_tag_id: number;
    notes?: string | null;
    super_tag_name?: string | null;
    sub_tag_name?: string | null;
}

export interface ITagUsage {
    accounts: number;
    posts: number;
    media: number;
    media_parts: number;
}

export interface ITagStat {
    tag_id: number;
    tag_name: string;
    tag_type_name: string | null;
    count: number;
}
