import React from 'react';
import {IComment} from "../../types/entities";
import {Link, Stack, Typography} from "@mui/material";
import dayjs from "dayjs";
import utc from 'dayjs/plugin/utc';
import AccountLink from "./AccountLink";
import {SHARE_URL_PARAM} from "../../services/linkSharing";

dayjs.extend(utc);

interface IProps {
    comment: IComment;
    /** DB id of the parent post — used to build the permalink. Inferred from comment.post_id if omitted. */
    postId?: number;
    shareToken?: string | null;
}

export default function Comment({comment, postId, shareToken}: IProps) {
    const dateRaw = comment.publication_date;
    const dateStr = dateRaw ? dayjs.utc(dateRaw).format('YYYY-MM-DD HH:mm') + ' UTC' : null;

    const resolvedPostId = postId ?? comment.post_id;
    const permalink = (() => {
        if (resolvedPostId == null || comment.id == null) return null;
        const params = new URLSearchParams();
        if (shareToken) params.append(SHARE_URL_PARAM, shareToken);
        params.append('comment_id', String(comment.id));
        return `/post/${resolvedPostId}?${params.toString()}`;
    })();

    return <Stack gap={0.25} sx={{borderLeft: '3px solid #ccc', paddingLeft: '0.75em'}}>
        <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
            <AccountLink
                url={comment.account_url}
                displayName={comment.account_display_name}
                accountId={comment.account_id}
            />
            {dateStr && (
                permalink
                    ? <Link href={permalink} underline="hover" color="text.secondary">
                        <Typography variant="caption">{dateStr}</Typography>
                    </Link>
                    : <Typography variant="caption" color="text.secondary">{dateStr}</Typography>
            )}
            {comment.parent_comment_id_on_platform && (
                <Typography variant="caption" color="text.secondary">
                    (reply to {comment.parent_comment_id_on_platform})
                </Typography>
            )}
        </Stack>
        {comment.text && <Typography variant="body2">{comment.text}</Typography>}
    </Stack>;
}
