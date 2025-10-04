export interface EntityBase {
    id?: number;
    created_at?: string; // ISO date string
    updated_at?: string;
    canonical_id?: number;
}

export interface Account extends EntityBase {
    id_on_platform?: string;
    url: string;
    display_name?: string;
    bio?: string;
    data?: any;
}

export interface Post extends EntityBase {
    id_on_platform?: string;
    url: string;
    account_id?: number;
    account_id_on_platform?: string;
    account_url?: string;
    publication_date?: string;
    caption?: string;
    data?: any;
}

export type MediaType = 'video' | 'audio' | 'image';

export interface Media extends EntityBase {
    id_on_platform?: string;
    url: string;
    post_id?: number;
    post_id_on_platform?: string;
    post_url?: string;
    local_url?: string;
    media_type: MediaType;
    data?: any;
}

export interface Comment extends EntityBase {
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

export interface Like extends EntityBase {
    id_on_platform?: string;
    post_id_on_platform?: string;
    post_url?: string;
    account_id_on_platform?: string;
    account_url?: string;
    data?: any;
}

export interface Follower extends EntityBase {
    follower_account_id: string;
    following_account_id: string;
    data?: any;
}

export interface SuggestedAccount extends EntityBase {
    context_account_id: string;
    suggested_account_id: string;
    data?: any;
}

export interface TaggedAccount extends EntityBase {
    tagged_account_id?: string;
    tagged_account_url?: string;
    context_account_id?: string;
    context_post_url?: string;
    context_media_url?: string;
    context_post_id_on_platform?: string;
    context_media_id_on_platform?: string;
    data?: any;
}

export interface ExtractedEntitiesFlattened {
    accounts: Account[];
    posts: Post[];
    media: Media[];
    comments: Comment[];
    likes: Like[];
    followers: Follower[];
    suggested_accounts: SuggestedAccount[];
    tagged_accounts: TaggedAccount[];
}

export interface MediaAndAssociatedEntities extends Media {
    media_parent_post?: PostAndAssociatedEntities;
}

export interface PostAndAssociatedEntities extends Post {
    post_author?: AccountAndAssociatedEntities;
    post_media: MediaAndAssociatedEntities[];
    post_comments: Comment[];
    post_likes: Like[];
    post_tagged_accounts: TaggedAccount[];
}

export interface AccountAndAssociatedEntities extends Account {
    account_posts: PostAndAssociatedEntities[];
    account_followers: Follower[];
    account_suggested_accounts: SuggestedAccount[];
}

export interface ExtractedEntitiesNested {
    accounts: AccountAndAssociatedEntities[];
    posts: PostAndAssociatedEntities[];
    media: MediaAndAssociatedEntities[];
}