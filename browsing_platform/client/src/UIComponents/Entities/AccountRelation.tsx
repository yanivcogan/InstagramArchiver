import React from 'react';
import {IAccountRelation} from "../../types/entities";
import {Chip, IconButton, Stack} from "@mui/material";
import LinkIcon from '@mui/icons-material/Link';
import AccountLink from "./AccountLink";
import {SHARE_URL_PARAM, getShareTokenFromHref} from "../../services/linkSharing";

interface IProps {
    relation: IAccountRelation;
    /** The account page this relation is being displayed on — used to build the permalink. */
    contextAccountId?: number;
}

export default function AccountRelation({relation, contextAccountId}: IProps) {
    const relLabel = relation.relation_type === 'suggested' ? 'suggested' : 'follows';
    const shareToken = getShareTokenFromHref();

    const permalink = (() => {
        if (contextAccountId == null || relation.id == null) return null;
        const params = new URLSearchParams();
        if (shareToken) params.append(SHARE_URL_PARAM, shareToken);
        params.append('relation_id', String(relation.id));
        return `/account/${contextAccountId}?${params.toString()}`;
    })();

    return <Stack direction="row" gap={0.75} alignItems="center">
        <AccountLink
            url={relation.follower_account_url}
            displayName={relation.follower_account_display_name}
            accountId={relation.follower_account_id}
        />
        <Chip
            label={relLabel}
            size="small"
            color={relation.relation_type === 'suggested' ? 'default' : 'primary'}
            variant="outlined"
        />
        <AccountLink
            url={relation.followed_account_url}
            displayName={relation.followed_account_display_name}
            accountId={relation.followed_account_id}
        />
        {permalink && (
            <IconButton size="small" href={permalink} color="default" sx={{ml: 'auto'}}>
                <LinkIcon fontSize="small"/>
            </IconButton>
        )}
    </Stack>;
}
