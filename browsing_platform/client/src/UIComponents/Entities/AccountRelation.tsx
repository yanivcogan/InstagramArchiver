import React from 'react';
import {IAccountRelation} from "../../types/entities";
import {Chip, IconButton, Stack} from "@mui/material";
import LinkIcon from '@mui/icons-material/Link';
import AccountLink from "./AccountLink";
import {getShareTokenFromHref, SHARE_URL_PARAM} from "../../services/linkSharing";
import {ITagWithType} from "../../types/tags";
import InlineTagsDisplay from "../Tags/InlineTagsDisplay";

interface IProps {
    relation: IAccountRelation;
    /** The account page this relation is being displayed on — used to build the permalink. */
    contextAccountId?: number;
    accountTagsMap?: Record<number, ITagWithType[]>;
}

export default function AccountRelation({relation, contextAccountId, accountTagsMap}: IProps) {
    const relLabel = relation.relation_type === 'suggested' ? 'suggested' : 'follows';
    const shareToken = getShareTokenFromHref();

    const permalink = (() => {
        if (contextAccountId == null || relation.id == null) return null;
        const params = new URLSearchParams();
        if (shareToken) params.append(SHARE_URL_PARAM, shareToken);
        params.append('relation_id', String(relation.id));
        return `/account/${contextAccountId}?${params.toString()}`;
    })();

    return <Stack direction="row" gap={0.75} alignItems="flex-start">
        <Stack>
            <AccountLink
                url={relation.follower_account_url}
                displayName={relation.follower_account_display_name}
                accountId={relation.follower_account_id}
            />
            <InlineTagsDisplay tags={relation.follower_account_id != null ? (accountTagsMap?.[relation.follower_account_id] ?? []) : []}/>
        </Stack>
        <Chip
            label={relLabel}
            size="small"
            color={relation.relation_type === 'suggested' ? 'default' : 'primary'}
            variant="outlined"
            sx={{mt: 0.25}}
        />
        <Stack>
            <AccountLink
                url={relation.followed_account_url}
                displayName={relation.followed_account_display_name}
                accountId={relation.followed_account_id}
            />
            <InlineTagsDisplay tags={relation.followed_account_id != null ? (accountTagsMap?.[relation.followed_account_id] ?? []) : []}/>
        </Stack>
        {permalink && (
            <IconButton size="small" href={permalink} color="default" sx={{ml: 'auto', mt: 0.25}}>
                <LinkIcon fontSize="small"/>
            </IconButton>
        )}
    </Stack>;
}
