import React from 'react';
import {IPostLike} from "../../types/entities";
import {IconButton} from "@mui/material";
import {GridColDef} from "@mui/x-data-grid";
import LinkIcon from '@mui/icons-material/Link';
import AccountLink, {accountLabel} from "./AccountLink";
import {SHARE_URL_PARAM} from "../../services/linkSharing";
import {ITagWithType} from "../../types/tags";
import InlineTagsDisplay from "../Tags/InlineTagsDisplay";

interface IColumnsOptions {
    /** DB id of the parent post — used to build the permalink. Inferred from like.post_id if omitted. */
    postId?: number;
    shareToken?: string | null;
    accountTagsMap?: Record<number, ITagWithType[]>;
}

function likePermalink(like: IPostLike, postId?: number, shareToken?: string | null): string | null {
    const resolvedPostId = postId ?? like.post_id;
    if (resolvedPostId == null || like.id == null) return null;
    const params = new URLSearchParams();
    if (shareToken) params.append(SHARE_URL_PARAM, shareToken);
    params.append('like_id', String(like.id));
    return `/post/${resolvedPostId}?${params.toString()}`;
}

export function buildLikeColumns({postId, shareToken, accountTagsMap}: IColumnsOptions): GridColDef[] {
    const tagsFor = (like: IPostLike): ITagWithType[] =>
        like.account_id != null ? (accountTagsMap?.[like.account_id] ?? []) : [];

    return [
        {
            field: 'account',
            headerName: 'Account',
            flex: 1,
            minWidth: 140,
            filterable: false,
            disableColumnMenu: true,
            valueGetter: (_, row: IPostLike) => accountLabel(row.account_url, row.account_display_name),
            renderCell: params => {
                const like = params.row as IPostLike;
                return <AccountLink
                    url={like.account_url}
                    displayName={like.account_display_name}
                    accountId={like.account_id}
                />;
            },
        },
        {
            field: 'tags',
            headerName: 'Tags',
            flex: 1.5,
            minWidth: 140,
            filterable: false,
            disableColumnMenu: true,
            valueGetter: (_, row: IPostLike) => tagsFor(row).map(t => t.name).join(', '),
            renderCell: params => <InlineTagsDisplay tags={tagsFor(params.row as IPostLike)}/>,
        },
        {
            field: 'permalink',
            headerName: '',
            width: 56,
            sortable: false,
            resizable: false,
            filterable: false,
            disableColumnMenu: true,
            renderCell: params => {
                const permalink = likePermalink(params.row as IPostLike, postId, shareToken);
                return permalink
                    ? <IconButton size="small" href={permalink} color="default">
                        <LinkIcon fontSize="small"/>
                    </IconButton>
                    : null;
            },
        },
    ];
}
