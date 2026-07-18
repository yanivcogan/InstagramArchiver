import React, {useEffect, useState} from 'react';
import {
    Badge,
    Box,
    CircularProgress,
    IconButton,
    ListItemText,
    Menu,
    MenuItem,
    Tooltip,
    Typography,
} from "@mui/material";
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import {fetchArchiverAccess} from "../../services/DataFetcher";
import {resolveCanViewArchiverAccess} from "../../services/archiverAccessPermission";
import {IArchiverAccessEntry} from "../../types/entities";
import ArchiverAccessList, {outboundStatus} from "./ArchiverAccessList";

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
        resolveCanViewArchiverAccess().then(v => {
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
            {!loading && entries !== null && <ArchiverAccessList entries={entries}/>}
        </Menu>
    </>;
}
