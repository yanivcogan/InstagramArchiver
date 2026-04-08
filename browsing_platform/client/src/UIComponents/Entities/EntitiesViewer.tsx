import React, {useMemo} from 'react';
import {
    IAccountAndAssociatedEntities,
    IExtractedEntitiesNested,
    IPostAndAssociatedEntities
} from "../../types/entities";
import {Stack} from "@mui/material";
import Post from "./Post";
import Account from "./Account";
import Media from "./Media";
import {EntityViewerConfig} from "./EntitiesViewerConfig";

interface IProps {
    entities: IExtractedEntitiesNested
    viewerConfig?: EntityViewerConfig
    highlightCommentId?: number
    highlightLikeId?: number
    highlightRelationId?: number
}

export default function EntitiesViewer({entities, viewerConfig, highlightCommentId, highlightLikeId, highlightRelationId}: IProps) {
    const sortedPosts = useMemo(() =>
        [...entities.posts].sort((a, b) =>
            (new Date(b.publication_date || 0).getTime()) - (new Date(a.publication_date || 0).getTime())
        ), [entities.posts]);

    const sortedAccounts = useMemo(() =>
        [...(entities.accounts ?? [])].sort(
            (a, b) => (b.account_posts?.length ?? 0) - (a.account_posts?.length ?? 0)
        ), [entities.accounts]);

    const initialAccountTagsMap = entities.account_tags ?? {};

    return <Stack gap={1}>
        {sortedAccounts.map((account: IAccountAndAssociatedEntities, index: number) =>
            <Account
                account={account}
                key={index}
                viewerConfig={viewerConfig}
                highlightCommentId={highlightCommentId}
                highlightLikeId={highlightLikeId}
                highlightRelationId={highlightRelationId}
                initialAccountTagsMap={initialAccountTagsMap}
            />
        )}
        {sortedPosts.map((post: IPostAndAssociatedEntities, index: number) =>
            <Post
                post={post}
                key={index}
                viewerConfig={viewerConfig}
                highlightCommentId={highlightCommentId}
                highlightLikeId={highlightLikeId}
                initialAccountTagsMap={initialAccountTagsMap}
            />
        )}
        {entities.media.map((media, index: number) =>
            <Media media={media} key={index} viewerConfig={viewerConfig}/>
        )}
    </Stack>
}
