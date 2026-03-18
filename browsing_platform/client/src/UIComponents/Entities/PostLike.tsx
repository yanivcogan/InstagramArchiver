import React from 'react';
import {IPostLike} from "../../types/entities";
import {IconButton, Stack} from "@mui/material";
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import LinkIcon from '@mui/icons-material/Link';
import AccountLink from "./AccountLink";
import {SHARE_URL_PARAM} from "../../services/linkSharing";

interface IProps {
    like: IPostLike;
    /** DB id of the parent post — used to build the permalink. Inferred from like.post_id if omitted. */
    postId?: number;
    shareToken?: string | null;
}

export default function PostLike({like, postId, shareToken}: IProps) {
    const resolvedPostId = postId ?? like.post_id;
    const permalink = (() => {
        if (resolvedPostId == null || like.id == null) return null;
        const params = new URLSearchParams();
        if (shareToken) params.append(SHARE_URL_PARAM, shareToken);
        params.append('like_id', String(like.id));
        return `/post/${resolvedPostId}?${params.toString()}`;
    })();

    return <Stack direction="row" gap={0.5} alignItems="center">
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
    </Stack>;
}
