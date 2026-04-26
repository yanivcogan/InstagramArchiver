import React from 'react';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import { ITaggedAccount } from '../../types/entities';
import AccountInteractionItem from './AccountInteractionItem';

export default function AccountTaggedInPost({ taggedAccount }: { taggedAccount: ITaggedAccount }) {
    return (
        <AccountInteractionItem
            Icon={LocalOfferIcon}
            color="warning"
            action="was tagged in a post"
            authorId={taggedAccount.post_author_account_id}
            authorLabel={taggedAccount.post_author_display_name || taggedAccount.post_author_url_suffix}
            postId={taggedAccount.post_id}
            postDate={taggedAccount.post_publication_date}
        />
    );
}
