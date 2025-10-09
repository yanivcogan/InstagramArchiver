export interface IEntityBase {
    id?: number;
    created_at?: string; // ISO date string
    updated_at?: string;
    canonical_id?: number;
}

export interface IAccount extends IEntityBase {
    id_on_platform?: string;
    url: string;
    display_name?: string;
    bio?: string;
    data?: any;
}

export interface IPost extends IEntityBase {
    id_on_platform?: string;
    url: string;
    account_id?: number;
    account_id_on_platform?: string;
    account_url?: string;
    publication_date?: string;
    caption?: string;
    data?: any;
}

export type EMediaType = 'video' | 'audio' | 'image';

export interface IMedia extends IEntityBase {
    id_on_platform?: string;
    url: string;
    post_id?: number;
    post_id_on_platform?: string;
    post_url?: string;
    local_url?: string;
    media_type: EMediaType;
    data?: any;
}

export interface IComment extends IEntityBase {
    id_on_platform?: string;
    url: string;
    post_id_on_platform: string;
    post_url?: string;
    account_id_on_platform?: string;
    account_url?: string;
    text?: string;
    publication_date?: string;
    data?: any;
}

export interface ILike extends IEntityBase {
    id_on_platform?: string;
    post_id_on_platform?: string;
    post_url?: string;
    account_id_on_platform?: string;
    account_url?: string;
    data?: any;
}

export interface IFollower extends IEntityBase {
    follower_account_id: string;
    following_account_id: string;
    data?: any;
}

export interface ISuggestedAccount extends IEntityBase {
    context_account_id: string;
    suggested_account_id: string;
    data?: any;
}

export interface ITaggedAccount extends IEntityBase {
    tagged_account_id?: string;
    tagged_account_url?: string;
    context_account_id?: string;
    context_post_url?: string;
    context_media_url?: string;
    context_post_id_on_platform?: string;
    context_media_id_on_platform?: string;
    data?: any;
}

export interface IExtractedEntitiesFlattened {
    accounts: IAccount[];
    posts: IPost[];
    media: IMedia[];
    comments: IComment[];
    likes: ILike[];
    followers: IFollower[];
    suggested_accounts: ISuggestedAccount[];
    tagged_accounts: ITaggedAccount[];
}

export interface IMediaAndAssociatedEntities extends IMedia {
    media_parent_post?: IPostAndAssociatedEntities;
}

export interface IPostAndAssociatedEntities extends IPost {
    post_author?: IAccountAndAssociatedEntities;
    post_media: IMediaAndAssociatedEntities[];
    post_comments: IComment[];
    post_likes: ILike[];
    post_tagged_accounts: ITaggedAccount[];
}

export interface IAccountAndAssociatedEntities extends IAccount {
    account_posts: IPostAndAssociatedEntities[];
    account_followers: IFollower[];
    account_suggested_accounts: ISuggestedAccount[];
}

export interface IExtractedEntitiesNested {
    accounts: IAccountAndAssociatedEntities[];
    posts: IPostAndAssociatedEntities[];
    media: IMediaAndAssociatedEntities[];
}

export interface ISessionAttachments {
    screen_recordings: string[];
    screen_shots: string[];
    wacz_archives: string[];
    har_archives: string[];
    hash_files: string[];
    timestamp_files: string[];
    other_files: string[];
}

export interface IArchiveSession {
    id?: number;
    create_date?: string;
    update_date?: string;
    external_id?: string;
    archived_url?: string;
    archive_location?: string;
    summary_html?: string;
    parsed_content?: number;
    structures?: Record<string, any>;
    metadata?: Record<string, any>;
    attachments?: ISessionAttachments;
    extracted_entities?: number;
    archiving_timestamp?: string;
    notes?: string;
    extraction_error?: string;
    source_type: number;
}

export interface IArchiveSessionWithEntities {
    session: IArchiveSession;
    entities: IExtractedEntitiesNested;
}