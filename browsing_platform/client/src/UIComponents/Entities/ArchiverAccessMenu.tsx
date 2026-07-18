import React, {useEffect, useState} from 'react';
import {
    Badge,
    Box,
    Chip,
    CircularProgress,
    IconButton,
    ListItemIcon,
    ListItemText,
    Menu,
    MenuItem,
    Stack,
    Tooltip,
    Typography,
} from "@mui/material";
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ScheduleIcon from '@mui/icons-material/Schedule';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import cookie from "js-cookie";
import server from "../../services/server";
import {fetchArchiverAccess} from "../../services/DataFetcher";
import {ArchiverAccessStatus, IArchiverAccessEntry} from "../../types/entities";

// Module-level cache: a page full of Account cards should trigger a single
// permissions request, not one per card. Keyed on the auth-token cookie so it
// invalidates automatically on logout/login (the token changes) instead of
// serving a prior user's permissions for the SPA session's lifetime.
let cachedToken: string | undefined;
let permissionPromise: Promise<boolean> | null = null;
const resolveCanView = (): Promise<boolean> => {
    const token = cookie.get("token");
    if (permissionPromise === null || token !== cachedToken) {
        cachedToken = token;
        permissionPromise = server.get("permissions/", {ignoreErrors: true})
            .then((res: any) => Boolean(res?.admin || res?.archiver))
            .catch(() => false);
    }
    return permissionPromise;
};

// The archiver's *outbound* relationship to this target, in priority order:
// already following (has access) wins over a pending request.
const outboundStatus = (entry: IArchiverAccessEntry): 'following' | 'requested' | 'none' => {
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
    accountId: number;
}

export default function ArchiverAccessMenu({accountId}: IProps) {
    const [canView, setCanView] = useState<boolean>(false);
    const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
    const [entries, setEntries] = useState<IArchiverAccessEntry[] | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(false);

    const loadEntries = async () => {
        if (entries !== null || loading) return;
        setLoading(true);
        setError(false);
        const result = await fetchArchiverAccess(accountId);
        // null signals a fetch failure (vs. an empty-but-successful roster);
        // leave entries null so reopening the menu retries.
        if (result === null) setError(true);
        else setEntries(result);
        setLoading(false);
    };

    // Resolve view permission on mount and, if allowed, fetch the access data
    // immediately (not lazily on menu open) so the badge count is ready and the
    // pending state can be shown up front.
    useEffect(() => {
        let alive = true;
        resolveCanView().then(v => {
            if (!alive) return;
            setCanView(v);
            if (v) void loadEntries();
        });
        return () => {
            alive = false;
        };
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // Reopening still retries if the initial fetch failed (loadEntries is a no-op
    // once data is loaded or a fetch is in flight).
    const handleOpen = (e: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(e.currentTarget);
        void loadEntries();
    };

    if (!canView) return null;

    const accessCount = entries?.filter(e => outboundStatus(e) === 'following').length ?? 0;

    return <>
        <Tooltip title="Archiver access">
            <IconButton size="small" color="info" onClick={handleOpen} aria-label="Archiver access">
                <Badge
                    color="success"
                    overlap="circular"
                    // While the request is pending, show a small spinner in the
                    // badge slot; afterwards, the count (hidden when zero).
                    invisible={!loading && accessCount === 0}
                    badgeContent={loading
                        ? <CircularProgress size={10} thickness={6} color="inherit"/>
                        : accessCount}
                >
                    <VpnKeyIcon fontSize="small"/>
                </Badge>
            </IconButton>
        </Tooltip>
        <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={() => setAnchorEl(null)}
            slotProps={{paper: {sx: {maxHeight: 360, minWidth: 260}}}}
        >
            <Box sx={{px: 2, pt: 1, pb: 0.5}}>
                <Typography variant="subtitle2">Archiver access</Typography>
                <Typography variant="caption" color="text.secondary">
                    Which archiving accounts can reach this account
                </Typography>
            </Box>
            {loading && (
                <Box sx={{display: 'flex', justifyContent: 'center', py: 2}}>
                    <CircularProgress size={20}/>
                </Box>
            )}
            {!loading && error && (
                <MenuItem disabled>
                    <ListItemText primary="Couldn't load archiver access — reopen to retry"/>
                </MenuItem>
            )}
            {!loading && !error && entries !== null && entries.length === 0 && (
                <MenuItem disabled>
                    <ListItemText primary="No archiver accounts registered"/>
                </MenuItem>
            )}
            {!loading && entries !== null && entries.map(entry => {
                const status = outboundStatus(entry);
                const meta = OUTBOUND_META[status];
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
        </Menu>
    </>;
}
