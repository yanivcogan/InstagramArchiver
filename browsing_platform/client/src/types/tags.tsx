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
}