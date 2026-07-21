import React from 'react';
import {IComment} from "../../types/entities";
import {Box, Link, Typography} from "@mui/material";
import {GridColDef} from "@mui/x-data-grid";
import dayjs from "dayjs";
import utc from 'dayjs/plugin/utc';
import AccountLink, {accountLabel} from "./AccountLink";
import {SHARE_URL_PARAM} from "../../services/linkSharing";
import {ITagWithType} from "../../types/tags";
import InlineTagsDisplay from "../Tags/InlineTagsDisplay";

dayjs.extend(utc);

interface IColumnsOptions {
    /** DB id of the parent post — used to build the permalink. Inferred from comment.post_id if omitted. */
    postId?: number;
    shareToken?: string | null;
    accountTagsMap?: Record<number, ITagWithType[]>;
}

function commentPermalink(comment: IComment, postId?: number, shareToken?: string | null): string | null {
    const resolvedPostId = postId ?? comment.post_id;
    if (resolvedPostId == null || comment.id == null) return null;
    const params = new URLSearchParams();
    if (shareToken) params.append(SHARE_URL_PARAM, shareToken);
    params.append('comment_id', String(comment.id));
    return `/post/${resolvedPostId}?${params.toString()}`;
}

export function buildCommentColumns({postId, shareToken, accountTagsMap}: IColumnsOptions): GridColDef[] {
    return [
        {
            field: 'author',
            headerName: 'Author',
            flex: 1.2,
            minWidth: 140,
            filterable: false,
            disableColumnMenu: true,
            valueGetter: (_, row: IComment) => accountLabel(row.account_url, row.account_display_name),
            renderCell: params => {
                const comment = params.row as IComment;
                return <Box>
                    <AccountLink
                        url={comment.account_url}
                        displayName={comment.account_display_name}
                        accountId={comment.account_id}
                    />
                    <InlineTagsDisplay tags={comment.account_id != null ? (accountTagsMap?.[comment.account_id] ?? []) : []}/>
                </Box>;
            },
        },
        {
            field: 'publication_date',
            headerName: 'Date',
            width: 155,
            filterable: false,
            disableColumnMenu: true,
            valueGetter: (_, row: IComment) => row.publication_date ?? '',
            renderCell: params => {
                const comment = params.row as IComment;
                const dateStr = comment.publication_date
                    ? dayjs.utc(comment.publication_date).format('YYYY-MM-DD HH:mm') + ' UTC'
                    : null;
                if (!dateStr) return <Typography variant="caption" color="text.disabled">–</Typography>;
                const permalink = commentPermalink(comment, postId, shareToken);
                return permalink
                    ? <Link href={permalink} underline="hover" color="text.secondary">
                        <Typography variant="caption">{dateStr}</Typography>
                    </Link>
                    : <Typography variant="caption" color="text.secondary">{dateStr}</Typography>;
            },
        },
        {
            field: 'text',
            headerName: 'Comment',
            flex: 2.5,
            minWidth: 200,
            filterable: false,
            disableColumnMenu: true,
            renderCell: params => {
                const comment = params.row as IComment;
                return <Box>
                    {comment.parent_comment_id_on_platform && (
                        <Typography variant="caption" color="text.secondary" display="block">
                            (reply to {comment.parent_comment_id_on_platform})
                        </Typography>
                    )}
                    {comment.text
                        ? <Typography variant="body2">{comment.text}</Typography>
                        : <Typography variant="caption" color="text.disabled" fontStyle="italic">(no text)</Typography>}
                </Box>;
            },
        },
    ];
}
