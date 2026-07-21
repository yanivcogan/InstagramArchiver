import React from 'react';
import {Link, Typography} from '@mui/material';
import {GridColDef} from '@mui/x-data-grid';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';

dayjs.extend(utc);

/** Fields shared by all three interaction row types (comments, likes, tagged-in). */
interface InteractionRow {
    post_author_account_id?: number;
    post_author_display_name?: string;
    post_author_url_suffix?: string;
    post_id?: number;
    post_publication_date?: string;
    text?: string;
}

/**
 * Columns for the account interactions panel sections. All sections share the
 * author/date columns so they stay visually consistent; only the comments
 * section adds a content column.
 */
export function buildInteractionColumns({withContent}: {withContent: boolean}): GridColDef[] {
    const columns: GridColDef[] = [
        {
            field: 'author',
            headerName: 'Post author',
            flex: 1,
            minWidth: 140,
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
    ];
    if (withContent) {
        columns.push({
            field: 'text',
            headerName: 'Content',
            flex: 2,
            minWidth: 200,
            renderCell: params => {
                const row = params.row as InteractionRow;
                return row.text
                    ? <Typography variant="body2" sx={{lineHeight: 1.45, fontSize: '0.8125rem'}}>{row.text}</Typography>
                    : null;
            },
        });
    }
    return columns;
}
