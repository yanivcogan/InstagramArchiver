import React from 'react';
import {ITaggedAccount} from "../../types/entities";
import {Chip, Link, Stack} from "@mui/material";
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import {accountLabel} from "./AccountLink";
import {ITagWithType} from "../../types/tags";
import InlineTagsDisplay from "../Tags/InlineTagsDisplay";

interface IProps {
    taggedAccount: ITaggedAccount;
    accountTags?: ITagWithType[];
}

export default function TaggedAccountChip({taggedAccount, accountTags}: IProps) {
    const label = accountLabel(taggedAccount.tagged_account_url, taggedAccount.tagged_account_display_name);

    const chip = <Chip
        icon={<LocalOfferIcon/>}
        label={label}
        size="small"
        variant="outlined"
        clickable={taggedAccount.tagged_account_id != null}
        component={taggedAccount.tagged_account_id != null ? Link : 'div'}
        href={taggedAccount.tagged_account_id != null ? `/account/${taggedAccount.tagged_account_id}` : undefined}
    />;

    if (accountTags && accountTags.length > 0) {
        return <Stack gap={0.25}>
            {chip}
            <InlineTagsDisplay tags={accountTags}/>
        </Stack>;
    }
    return chip;
}
