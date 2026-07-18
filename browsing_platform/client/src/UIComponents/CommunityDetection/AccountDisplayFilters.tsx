import React, {useState} from 'react';
import {
    Badge,
    Box,
    Button,
    MenuItem,
    Popover,
    Stack,
    TextField,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    Typography,
} from '@mui/material';
import FilterListIcon from '@mui/icons-material/FilterList';
import NumberField from '../MUINumberField/NumberField';

// Display-only filters for the community-detection account lists. These visually
// hide non-matching entries (they never remove items). A single value drives the
// controls shown in both the kernel and candidates section headers.

export type ArchiverFilterMode =
    'all' | 'followed_by_any' | 'followed_by' | 'not_followed' | 'not_followed_or_requested';

export interface DisplayFilters {
    relationsMode: 'all' | 'over' | 'under';
    relationsThreshold: number;
    postsMode: 'all' | 'has' | 'none';
    archiverMode: ArchiverFilterMode;
    // Target archiver label when archiverMode === 'followed_by'.
    archiverLabel: string | null;
}

export const DEFAULT_DISPLAY_FILTERS: DisplayFilters = {
    relationsMode: 'all',
    relationsThreshold: 0,
    postsMode: 'all',
    archiverMode: 'all',
    archiverLabel: null,
};

export function isDisplayFilterActive(f: DisplayFilters): boolean {
    return f.relationsMode !== 'all' || f.postsMode !== 'all' || f.archiverMode !== 'all';
}

const ARCHIVER_MODE_OPTIONS: {value: ArchiverFilterMode; label: string}[] = [
    {value: 'all', label: 'All'},
    {value: 'followed_by_any', label: 'Followed by any archiver'},
    {value: 'followed_by', label: 'Followed by…'},
    {value: 'not_followed', label: 'Not followed by any archiver'},
    {value: 'not_followed_or_requested', label: 'Not followed or requested by any'},
];

interface AccountDisplayFiltersProps {
    value: DisplayFilters;
    onChange: (next: DisplayFilters) => void;
    // Archiver-access filters are shown only to permitted (archiver/admin) viewers.
    showArchiverSection?: boolean;
    // Options for the "Followed by…" particular-archiver picker.
    archiverLabels?: string[];
}

export default function AccountDisplayFilters({
                                                  value,
                                                  onChange,
                                                  showArchiverSection,
                                                  archiverLabels = [],
                                              }: AccountDisplayFiltersProps) {
    const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
    const active = isDisplayFilterActive(value);

    return (
        <>
            <Tooltip title="Filter visible accounts">
                <Badge color="primary" variant="dot" invisible={!active} overlap="circular">
                    <Button
                        size="small"
                        variant={active ? 'contained' : 'outlined'}
                        startIcon={<FilterListIcon/>}
                        onClick={e => setAnchorEl(e.currentTarget)}
                        sx={{flexShrink: 0}}
                    >
                        Filters
                    </Button>
                </Badge>
            </Tooltip>
            <Popover
                open={anchorEl !== null}
                anchorEl={anchorEl}
                onClose={() => setAnchorEl(null)}
                anchorOrigin={{vertical: 'bottom', horizontal: 'right'}}
                transformOrigin={{vertical: 'top', horizontal: 'right'}}
            >
                <Stack gap={2} sx={{p: 2, minWidth: 280}}>
                    {/* Account relations (followers + following) */}
                    <Box>
                        <Typography variant="caption" sx={{
                            color: 'text.disabled', fontSize: '0.65rem',
                            letterSpacing: '0.08em', textTransform: 'uppercase',
                        }}>
                            Account relations (followers + following)
                        </Typography>
                        <Stack direction="row" gap={1} alignItems="center" sx={{mt: 0.75}}>
                            <ToggleButtonGroup
                                size="small"
                                exclusive
                                value={value.relationsMode}
                                onChange={(_, v) => {
                                    if (v !== null) onChange({...value, relationsMode: v});
                                }}
                            >
                                <ToggleButton value="all">All</ToggleButton>
                                <ToggleButton value="over">&gt; N</ToggleButton>
                                <ToggleButton value="under">&lt; N</ToggleButton>
                            </ToggleButtonGroup>
                            <NumberField
                                label="N"
                                size="small"
                                min={0}
                                step={1}
                                value={value.relationsThreshold}
                                disabled={value.relationsMode === 'all'}
                                onValueChange={v => onChange({...value, relationsThreshold: v ?? 0})}
                                sx={{width: 90}}
                            />
                        </Stack>
                    </Box>

                    {/* Posts */}
                    <Box>
                        <Typography variant="caption" sx={{
                            color: 'text.disabled', fontSize: '0.65rem',
                            letterSpacing: '0.08em', textTransform: 'uppercase',
                        }}>
                            Posts
                        </Typography>
                        <Box sx={{mt: 0.75}}>
                            <ToggleButtonGroup
                                size="small"
                                exclusive
                                value={value.postsMode}
                                onChange={(_, v) => {
                                    if (v !== null) onChange({...value, postsMode: v});
                                }}
                            >
                                <ToggleButton value="all">All</ToggleButton>
                                <ToggleButton value="has">Has posts</ToggleButton>
                                <ToggleButton value="none">No posts</ToggleButton>
                            </ToggleButtonGroup>
                        </Box>
                    </Box>

                    {/* Archiver access (archiver/admin viewers only) */}
                    {showArchiverSection && (
                        <Box>
                            <Typography variant="caption" sx={{
                                color: 'text.disabled', fontSize: '0.65rem',
                                letterSpacing: '0.08em', textTransform: 'uppercase',
                            }}>
                                Archiver access
                            </Typography>
                            <Stack gap={1} sx={{mt: 0.75}}>
                                <TextField
                                    select
                                    size="small"
                                    value={value.archiverMode}
                                    onChange={e => {
                                        const mode = e.target.value as ArchiverFilterMode;
                                        onChange({
                                            ...value,
                                            archiverMode: mode,
                                            // Seed / clear the particular-archiver picker with the mode.
                                            archiverLabel: mode === 'followed_by'
                                                ? (value.archiverLabel ?? archiverLabels[0] ?? null)
                                                : null,
                                        });
                                    }}
                                >
                                    {ARCHIVER_MODE_OPTIONS.map(o => (
                                        <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
                                    ))}
                                </TextField>
                                {value.archiverMode === 'followed_by' && (
                                    <TextField
                                        select
                                        size="small"
                                        label="Archiver"
                                        value={value.archiverLabel ?? ''}
                                        onChange={e => onChange({...value, archiverLabel: e.target.value || null})}
                                        disabled={archiverLabels.length === 0}
                                        helperText={archiverLabels.length === 0 ? 'No archivers in results' : undefined}
                                    >
                                        {archiverLabels.map(label => (
                                            <MenuItem key={label} value={label}>{label}</MenuItem>
                                        ))}
                                    </TextField>
                                )}
                            </Stack>
                        </Box>
                    )}

                    {active && (
                        <Button size="small" onClick={() => onChange(DEFAULT_DISPLAY_FILTERS)}>
                            Clear filters
                        </Button>
                    )}
                </Stack>
            </Popover>
        </>
    );
}
