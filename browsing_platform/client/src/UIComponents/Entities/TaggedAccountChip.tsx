import React from 'react';
import {ITaggedAccount} from "../../types/entities";
import {Chip, Link} from "@mui/material";
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import {accountLabel} from "./AccountLink";

interface IProps {
    taggedAccount: ITaggedAccount;
}

export default function TaggedAccountChip({taggedAccount}: IProps) {
    const label = accountLabel(taggedAccount.tagged_account_url, taggedAccount.tagged_account_display_name);

    return <Chip
        icon={<LocalOfferIcon/>}
        label={label}
        size="small"
        variant="outlined"
        clickable={taggedAccount.tagged_account_id != null}
        component={taggedAccount.tagged_account_id != null ? Link : 'div'}
        href={taggedAccount.tagged_account_id != null ? `/account/${taggedAccount.tagged_account_id}` : undefined}
    />
}
