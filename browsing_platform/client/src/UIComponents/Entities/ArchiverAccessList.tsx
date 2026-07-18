import React from 'react';
import {Chip, ListItemIcon, ListItemText, MenuItem, Stack, Tooltip} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ScheduleIcon from '@mui/icons-material/Schedule';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import {ArchiverAccessStatus, IArchiverAccessEntry} from '../../types/entities';

// The archiver's *outbound* relationship to this target, in priority order:
// already following (has access) wins over a pending request.
export const outboundStatus = (entry: IArchiverAccessEntry): 'following' | 'requested' | 'none' => {
    const has = (s: ArchiverAccessStatus) => entry.statuses.some(x => x.status === s);
    if (has('following')) return 'following';
    if (has('requested')) return 'requested';
    return 'none';
};

const OUTBOUND_META = {
    following: {icon: <CheckCircleIcon fontSize="small" color="success"/>, label: 'Following (has access)'},
    requested: {icon: <ScheduleIcon fontSize="small" color="warning"/>, label: 'Requested access'},
    none: {icon: <RadioButtonUncheckedIcon fontSize="small" color="disabled"/>, label: 'No relationship'},
} as const;

interface IProps {
    entries: IArchiverAccessEntry[];
}

// Renders one row per archiver account: a leading outbound-relationship icon
// (following / requested / none) and the label, with trailing chips for the
// inbound relationship (the target follows / has requested the archiver back).
// Shared by ArchiverAccessMenu (account page) and ArchiverAccessChip's tooltip
// (community detection).
export default function ArchiverAccessList({entries}: IProps) {
    return <>
        {entries.map(entry => {
            const meta = OUTBOUND_META[outboundStatus(entry)];
            const followedBy = entry.statuses.some(x => x.status === 'followed_by');
            const requestedFrom = entry.statuses.some(x => x.status === 'follow_requests_from');
            return <MenuItem key={entry.label} disableRipple sx={{cursor: 'default'}}>
                <ListItemIcon>
                    <Tooltip title={meta.label}>{meta.icon}</Tooltip>
                </ListItemIcon>
                <ListItemText primary={entry.label}/>
                {(followedBy || requestedFrom) && (
                    <Stack direction="row" gap={0.5} sx={{ml: 1}}>
                        {followedBy && <Chip size="small" variant="outlined" label="follows back"/>}
                        {requestedFrom && <Chip size="small" variant="outlined" label="requested"/>}
                    </Stack>
                )}
            </MenuItem>;
        })}
    </>;
}
