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
    notes_recommended?: boolean;
}

export interface ITagType {
    id?: number;
    name: string;
    description?: string | null;
    notes?: string | null;
    entity_affinity?: string[] | null;
    quick_access?: boolean;
}

interface ITagParent {
    id: number;
    name: string;
}

export interface ITagDetail {
    id?: number;
    name: string;
    description?: string | null;
    tag_type_id?: number | null;
    tag_type_name?: string | null;
    quick_access?: boolean;
    omit_from_tag_type_dropdown?: boolean;
    notes_recommended?: boolean;
    parents?: ITagParent[];
}

export interface IQuickAccessTypeDropdown {
    type_id: number;
    type_name: string;
    tags: ITagWithType[];
    hierarchy?: Array<{super_tag_id: number; sub_tag_id: number}>;
}

export interface IQuickAccessData {
    individual_tags: ITagWithType[];
    type_dropdowns: IQuickAccessTypeDropdown[];
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

// ── Tag Import ────────────────────────────────────────────────────────────────

export interface ITagImportParseError {
    field: string;
    message: string;
}

export interface ITagImportRowParsed {
    row_index: number;
    name: string;
    tag_type: string | null;
    description: string | null;
    quick_access: boolean;
    parents: string[];
    parse_errors: ITagImportParseError[];
}

export interface ITagImportRowInput {
    name: string;
    tag_type: string | null;
    description: string | null;
    quick_access: boolean;
    parents: string[];
}

export interface ITagRelationshipResult {
    parent_name: string;
    status: 'added' | 'exists' | 'cycle' | 'parent_not_found';
}

export interface ITagImportRowResult {
    row_index: number;
    status: 'created' | 'existing' | 'error';
    tag_id: number | null;
    tag_name: string;
    errors: string[];
    relationships: ITagRelationshipResult[];
}

export interface ITagImportSummary {
    created: number;
    existing: number;
    errors: number;
    relationships_added: number;
    cycles_skipped: number;
}

export interface ITagImportExecuteResponse {
    results: ITagImportRowResult[];
    summary: ITagImportSummary;
}

// ── Annotation Import ─────────────────────────────────────────────────────────

export interface IResolvedAnnotationRow {
    row_index: number;
    entity_type: string;
    entity_raw: string;
    entity_id: number | null;
    entity_display: string | null;
    tag_name: string;
    tag_type: string | null;
    tag_id: number | null;
    notes: string | null;
    parse_errors: string[];
}

export interface IAnnotationImportRowInput {
    entity_type: string;
    entity: string;
    tag: string;
    tag_type: string | null;
    notes: string | null;
}

export interface IAnnotationImportRowResult {
    row_index: number;
    status: 'added' | 'exists' | 'error';
    errors: string[];
}

export interface IAnnotationImportSummary {
    added: number;
    exists: number;
    errors: number;
}

export interface IAnnotationImportExecuteResponse {
    results: IAnnotationImportRowResult[];
    summary: IAnnotationImportSummary;
}
