import React from 'react';
import {Box, Chip, Tooltip, Typography} from '@mui/material';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import {IArchiverAccessEntry} from '../../types/entities';
import ArchiverAccessList, {outboundStatus} from '../Entities/ArchiverAccessList';

interface IProps {
    // null/undefined => caller is not permitted to see archiver access; render nothing.
    // empty array    => permitted, but no archivers hold any relationship ("not followed").
    entries?: IArchiverAccessEntry[] | null;
}

// The alphabetically-first label (the one the chip names) — cheaper and clearer
// than sorting when only the min and the count are needed.
const firstLabel = (entries: IArchiverAccessEntry[]): string =>
    entries.map(e => e.label).reduce((a, b) => (a.localeCompare(b) <= 0 ? a : b));

// Compact "who can reach this account" indicator for the community-detection
// lists. The label names at most one archiver (alphabetically first) and hints
// at the rest with "+N"; hovering reveals the full roster via ArchiverAccessList.
// Buckets by the shared outboundStatus (following beats requested), so the
// following>requested precedence stays consistent with the tooltip/menu.
export default function ArchiverAccessChip({entries}: IProps) {
    if (entries == null) return null;

    const suffix = (n: number) => (n > 1 ? ` +${n - 1}` : '');
    const followers = entries.filter(e => outboundStatus(e) === 'following');

    let label: string;
    let color: 'success' | 'warning' | 'default';
    if (followers.length > 0) {
        label = `followed by ${firstLabel(followers)}${suffix(followers.length)}`;
        color = 'success';
    } else {
        const requesters = entries.filter(e => outboundStatus(e) === 'requested');
        if (requesters.length > 0) {
            label = `requested by ${firstLabel(requesters)}${suffix(requesters.length)}`;
            color = 'warning';
        } else {
            label = 'not followed';
            color = 'default';
        }
    }

    const tooltip = entries.length === 0
        ? <Box sx={{px: 1.5, py: 1}}>
            <Typography variant="caption" color="text.secondary">No archiver accounts registered</Typography>
        </Box>
        : <ArchiverAccessList entries={entries}/>;

    return (
        <Tooltip
            arrow
            title={tooltip}
            slotProps={{
                tooltip: {
                    sx: {
                        bgcolor: 'background.paper',
                        color: 'text.primary',
                        border: '1px solid',
                        borderColor: 'divider',
                        boxShadow: 3,
                        maxWidth: 'none',
                        p: 0,
                    },
                },
                arrow: {sx: {color: 'background.paper'}},
            }}
        >
            <Chip
                icon={<VpnKeyIcon/>}
                label={label}
                size="small"
                color={color}
                variant={color === 'default' ? 'outlined' : 'filled'}
                sx={{height: 18, '& .MuiChip-label': {px: 0.75, fontSize: '0.6rem'}, '& .MuiChip-icon': {fontSize: '0.8rem', ml: 0.5}}}
            />
        </Tooltip>
    );
}
