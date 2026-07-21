import React from 'react';
import {IAccountRelation} from "../../types/entities";
import {Box, Chip, IconButton, Stack, Tooltip, Typography} from "@mui/material";
import {GridColDef} from "@mui/x-data-grid";
import LinkIcon from '@mui/icons-material/Link';
import AccountLink, {accountLabel} from "./AccountLink";
import {getShareTokenFromHref, SHARE_URL_PARAM} from "../../services/linkSharing";
import {ITagWithType} from "../../types/tags";
import InlineTagsDisplay from "../Tags/InlineTagsDisplay";

interface OrientedAccount {
    id?: number;
    url?: string;
    displayName?: string;
}

interface OrientedRelation {
    /** false → contextAccountId matched neither side; render both parties. */
    oriented: boolean;
    other?: OrientedAccount;
    /** Chip text, phrased with the viewed account as the subject (e.g. "follows" = viewed follows other). */
    label: string;
    /** Tooltip text, always in the raw server direction. */
    sentence: string;
}

export function orientRelation(relation: IAccountRelation, contextAccountId?: number): OrientedRelation {
    const isSuggested = relation.relation_type === 'suggested';
    const baseLabel = isSuggested ? 'suggested' : 'follows';
    const sentence = `${accountLabel(relation.follower_account_url, relation.follower_account_display_name)}`
        + ` ${isSuggested ? 'suggested for' : 'follows'} `
        + `${accountLabel(relation.followed_account_url, relation.followed_account_display_name)}`;

    if (contextAccountId != null && relation.follower_account_id === contextAccountId) {
        return {
            oriented: true,
            other: {
                id: relation.followed_account_id,
                url: relation.followed_account_url,
                displayName: relation.followed_account_display_name,
            },
            label: isSuggested ? 'suggested' : 'follows',
            sentence,
        };
    }
    if (contextAccountId != null && relation.followed_account_id === contextAccountId) {
        return {
            oriented: true,
            other: {
                id: relation.follower_account_id,
                url: relation.follower_account_url,
                displayName: relation.follower_account_display_name,
            },
            label: isSuggested ? 'suggested' : 'followed by',
            sentence,
        };
    }
    return {oriented: false, label: baseLabel, sentence};
}

interface IColumnsOptions {
    /** The account page these relations are displayed on — orients directionality and builds permalinks. */
    contextAccountId?: number;
    accountTagsMap?: Record<number, ITagWithType[]>;
}

export function buildRelationColumns({contextAccountId, accountTagsMap}: IColumnsOptions): GridColDef[] {
    const shareToken = getShareTokenFromHref();

    const tagsFor = (accountId?: number): ITagWithType[] =>
        accountId != null ? (accountTagsMap?.[accountId] ?? []) : [];

    return [
        {
            field: 'account',
            headerName: 'Account',
            flex: 1.2,
            minWidth: 160,
            valueGetter: (_, row: IAccountRelation) => {
                const {oriented, other} = orientRelation(row, contextAccountId);
                return oriented
                    ? accountLabel(other?.url, other?.displayName)
                    : `${accountLabel(row.follower_account_url, row.follower_account_display_name)}`
                        + ` → ${accountLabel(row.followed_account_url, row.followed_account_display_name)}`;
            },
            renderCell: params => {
                const relation = params.row as IAccountRelation;
                const {oriented, other} = orientRelation(relation, contextAccountId);
                if (oriented) {
                    return <Box>
                        <AccountLink
                            url={other?.url}
                            displayName={other?.displayName}
                            accountId={other?.id}
                        />
                        <InlineTagsDisplay tags={tagsFor(other?.id)}/>
                    </Box>;
                }
                return <Box>
                    <Stack direction="row" gap={0.5} alignItems="center" flexWrap="wrap">
                        <AccountLink
                            url={relation.follower_account_url}
                            displayName={relation.follower_account_display_name}
                            accountId={relation.follower_account_id}
                        />
                        <Typography variant="caption" color="text.secondary">→</Typography>
                        <AccountLink
                            url={relation.followed_account_url}
                            displayName={relation.followed_account_display_name}
                            accountId={relation.followed_account_id}
                        />
                    </Stack>
                    <InlineTagsDisplay tags={tagsFor(relation.follower_account_id)}/>
                    <InlineTagsDisplay tags={tagsFor(relation.followed_account_id)}/>
                </Box>;
            },
        },
        {
            field: 'relation',
            headerName: 'Relation',
            flex: 1,
            minWidth: 120,
            valueGetter: (_, row: IAccountRelation) => orientRelation(row, contextAccountId).label,
            renderCell: params => {
                const relation = params.row as IAccountRelation;
                const {label, sentence} = orientRelation(relation, contextAccountId);
                return <Tooltip title={sentence}>
                    <Chip
                        label={label}
                        size="small"
                        color={relation.relation_type === 'suggested' ? 'default' : 'primary'}
                        variant="outlined"
                    />
                </Tooltip>;
            },
        },
        {
            field: 'permalink',
            headerName: '',
            width: 56,
            sortable: false,
            resizable: false,
            renderCell: params => {
                const relation = params.row as IAccountRelation;
                if (contextAccountId == null || relation.id == null) return null;
                const urlParams = new URLSearchParams();
                if (shareToken) urlParams.append(SHARE_URL_PARAM, shareToken);
                urlParams.append('relation_id', String(relation.id));
                return <IconButton size="small" href={`/account/${contextAccountId}?${urlParams.toString()}`} color="default">
                    <LinkIcon fontSize="small"/>
                </IconButton>;
            },
        },
    ];
}
