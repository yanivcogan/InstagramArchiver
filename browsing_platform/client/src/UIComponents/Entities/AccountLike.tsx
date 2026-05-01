import React from 'react';
import ThumbUpOutlinedIcon from '@mui/icons-material/ThumbUpOutlined';
import { IPostLike } from '../../types/entities';
import AccountInteractionItem from './AccountInteractionItem';

export default function AccountLike({ like }: { like: IPostLike }) {
    return (
        <AccountInteractionItem
            Icon={ThumbUpOutlinedIcon}
            color="error"
            action="liked a post"
            authorId={like.post_author_account_id}
            authorLabel={like.post_author_display_name || like.post_author_url_suffix}
            postId={like.post_id}
            postDate={like.post_publication_date}
        />
    );
}
