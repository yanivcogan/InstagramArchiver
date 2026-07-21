import React from 'react';
import {Link, Stack, Typography} from '@mui/material';
import {GridColDef} from '@mui/x-data-grid';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import ThumbUpOutlinedIcon from '@mui/icons-material/ThumbUpOutlined';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';

dayjs.extend(utc);

export type InteractionType = 'comment' | 'like' | 'tagged';

/** Fields shared by all three interaction row types (comments, likes, tagged-in). */
interface InteractionRow {
    interaction_type: InteractionType;
    post_author_account_id?: number;
    post_author_display_name?: string;
    post_author_url_suffix?: string;
    post_id?: number;
    post_publication_date?: string;
    text?: string;
}

const TYPE_DISPLAY: Record<InteractionType, {Icon: React.ComponentType<{sx?: object}>; color: string}> = {
    comment: {Icon: ChatBubbleOutlineIcon, color: 'primary.main'},
    like: {Icon: ThumbUpOutlinedIcon, color: 'error.main'},
    tagged: {Icon: LocalOfferIcon, color: 'warning.main'},
};

/**
 * Columns for the unified account interactions grid. The Type column is
 * filterable (client-side, via the column header menu); the rest are not.
 */
export function buildInteractionColumns(): GridColDef[] {
    return [
        {
            field: 'interaction_type',
            headerName: 'Type',
            width: 110,
            type: 'singleSelect',
            valueOptions: ['comment', 'like', 'tagged'],
            renderCell: params => {
                const row = params.row as InteractionRow;
                const display = TYPE_DISPLAY[row.interaction_type];
                if (!display) return null;
                const {Icon, color} = display;
                return <Stack direction="row" gap={0.5} alignItems="center">
                    <Icon sx={{fontSize: 14, color}}/>
                    <Typography variant="caption">{row.interaction_type}</Typography>
                </Stack>;
            },
        },
        {
            field: 'author',
            headerName: 'Post author',
            flex: 1,
            minWidth: 140,
            filterable: false,
            disableColumnMenu: true,
            valueGetter: (_, row: InteractionRow) =>
                row.post_author_display_name || row.post_author_url_suffix || '',
            renderCell: params => {
                const row = params.row as InteractionRow;
                const label = row.post_author_display_name || row.post_author_url_suffix;
                if (!row.post_author_account_id && !label) {
                    return <Typography variant="caption" color="text.disabled">–</Typography>;
                }
                return row.post_author_account_id
                    ? <Link
                        href={`/account/${row.post_author_account_id}`}
                        underline="hover"
                        sx={{color: 'text.primary', fontWeight: 600}}
                    >
                        <Typography variant="caption" component="span">{label || 'unknown'}</Typography>
                    </Link>
                    : <Typography variant="caption" sx={{fontWeight: 600, color: 'text.primary'}}>{label}</Typography>;
            },
        },
        {
            field: 'post_publication_date',
            headerName: 'Post date',
            width: 110,
            filterable: false,
            disableColumnMenu: true,
            valueGetter: (_, row: InteractionRow) => row.post_publication_date ?? '',
            renderCell: params => {
                const row = params.row as InteractionRow;
                const formattedDate = row.post_publication_date
                    ? dayjs.utc(row.post_publication_date).format('YYYY-MM-DD')
                    : null;
                if (!formattedDate) return <Typography variant="caption" color="text.disabled">–</Typography>;
                return row.post_id
                    ? <Link href={`/post/${row.post_id}`} underline="hover" color="text.secondary">
                        <Typography variant="caption" component="span" sx={{fontFamily: 'monospace'}}>
                            {formattedDate}
                        </Typography>
                    </Link>
                    : <Typography variant="caption" sx={{fontFamily: 'monospace'}}>{formattedDate}</Typography>;
            },
        },
        {
            field: 'text',
            headerName: 'Content',
            flex: 2,
            minWidth: 200,
            filterable: false,
            disableColumnMenu: true,
            renderCell: params => {
                const row = params.row as InteractionRow;
                return row.text
                    ? <Typography variant="body2" sx={{lineHeight: 1.45, fontSize: '0.8125rem'}}>{row.text}</Typography>
                    : null;
            },
        },
    ];
}
