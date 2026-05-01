import React from 'react';
import {IPostLike} from "../../types/entities";
import {IconButton, Stack} from "@mui/material";
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import LinkIcon from '@mui/icons-material/Link';
import AccountLink from "./AccountLink";
import {SHARE_URL_PARAM} from "../../services/linkSharing";
import {ITagWithType} from "../../types/tags";
import InlineTagsDisplay from "../Tags/InlineTagsDisplay";

interface IProps {
    like: IPostLike;
    /** DB id of the parent post — used to build the permalink. Inferred from like.post_id if omitted. */
    postId?: number;
    shareToken?: string | null;
    accountTagsMap?: Record<number, ITagWithType[]>;
}

export default function PostLike({like, postId, shareToken, accountTagsMap}: IProps) {
    const resolvedPostId = postId ?? like.post_id;
    const permalink = (() => {
        if (resolvedPostId == null || like.id == null) return null;
        const params = new URLSearchParams();
        if (shareToken) params.append(SHARE_URL_PARAM, shareToken);
        params.append('like_id', String(like.id));
        return `/post/${resolvedPostId}?${params.toString()}`;
    })();

    const tags = like.account_id != null ? (accountTagsMap?.[like.account_id] ?? []) : [];
    return <Stack gap={0.25}>
        <Stack direction="row" gap={0.5} alignItems="center">
            <ThumbUpIcon fontSize="small" color="action"/>
            <AccountLink
                url={like.account_url}
                displayName={like.account_display_name}
                accountId={like.account_id}
            />
            {permalink && (
                <IconButton size="small" href={permalink} color="default" sx={{ml: 'auto'}}>
                    <LinkIcon fontSize="small"/>
                </IconButton>
            )}
        </Stack>
        <InlineTagsDisplay tags={tags}/>
    </Stack>;
}
