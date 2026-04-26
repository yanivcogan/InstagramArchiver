import React from 'react';
import { Typography } from '@mui/material';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import { IComment } from '../../types/entities';
import AccountInteractionItem from './AccountInteractionItem';

export default function AccountComment({ comment }: { comment: IComment }) {
    return (
        <AccountInteractionItem
            Icon={ChatBubbleOutlineIcon}
            color="primary"
            action="commented on a post"
            authorId={comment.post_author_account_id}
            authorLabel={comment.post_author_display_name || comment.post_author_url_suffix}
            postId={comment.post_id}
            postDate={comment.post_publication_date}
        >
            {comment.text && (
                <Typography
                    variant="body2"
                    sx={{ mt: 0.5, ml: '22px', lineHeight: 1.45, fontSize: '0.8125rem' }}
                >
                    {comment.text}
                </Typography>
            )}
        </AccountInteractionItem>
    );
}
