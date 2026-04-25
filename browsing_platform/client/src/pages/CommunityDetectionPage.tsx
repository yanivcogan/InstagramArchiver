import React, {useCallback, useEffect, useRef, useState} from 'react';
import {
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Collapse,
    Divider,
    List,
    ListItemButton,
    ListItemText,
    OutlinedInput,
    Paper,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SearchIcon from '@mui/icons-material/Search';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import TopNavBar from '../UIComponents/TopNavBar/TopNavBar';
import {SearchResultThumbnails} from '../UIComponents/SearchResults/SearchResultParts';
import NumberField from '../UIComponents/MUINumberField/NumberField';
import {
    CandidateAccount,
    CommunityCandidatesResponse,
    DEFAULT_TIE_WEIGHTS,
    fetchCommunityCandidates,
    SearchResult,
    searchData,
    TieWeights,
} from '../services/DataFetcher';

function candidateTitle(c: Pick<CandidateAccount, 'id' | 'url_suffix' | 'display_name'>): string {
    return c.display_name
        ? `${c.url_suffix} (${c.display_name})`
        : (c.url_suffix ?? `Account ${c.id}`);
}

// ── Candidate card ────────────────────────────────────────────────────────────

interface CandidateCardProps {
    candidate: CandidateAccount;
    onAddToKernel: () => void;
    onExclude: () => void;
}

function CandidateCard({candidate, onAddToKernel, onExclude}: CandidateCardProps) {
    const title = candidateTitle(candidate);

    return (
        <Card variant="outlined">
            <CardContent sx={{pb: '12px !important'}}>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={2}>
                    <Box sx={{flex: 1, minWidth: 0}}>
                        <a href={`/account/${candidate.id}`} style={{textDecoration: 'none', color: 'inherit'}}>
                            <Typography variant="h6" sx={{wordBreak: 'break-word'}}>{title}</Typography>
                        </a>
                        {candidate.bio && (
                            <Typography variant="body2" color="text.secondary" sx={{mt: 0.25}}>
                                {candidate.bio}
                            </Typography>
                        )}
                        <SearchResultThumbnails
                            thumbnails={candidate.thumbnails}
                            totalCount={candidate.media_count}
                        />
                        <Stack direction="row" gap={0.75} flexWrap="wrap" sx={{mt: 0.75}}>
                            <Chip
                                label={`Score: ${candidate.score % 1 === 0 ? candidate.score : candidate.score.toFixed(2)}`}
                                size="small"
                                color="primary"
                                variant="outlined"
                            />
                            <Chip
                                label={`${candidate.kernel_connections} kernel connection${candidate.kernel_connections !== 1 ? 's' : ''}`}
                                size="small"
                                variant="outlined"
                            />
                            {candidate.is_verified && (
                                <Chip label="Verified" size="small" color="info" variant="outlined"/>
                            )}
                        </Stack>
                    </Box>
                    <Stack direction="column" gap={1} sx={{flexShrink: 0}}>
                        <Button size="small" variant="outlined" onClick={onAddToKernel}>
                            Add to Kernel
                        </Button>
                        <Button size="small" variant="outlined" color="warning" onClick={onExclude}>
                            Exclude
                        </Button>
                    </Stack>
                </Stack>
            </CardContent>
        </Card>
    );
}

// ── Tie weight labels ─────────────────────────────────────────────────────────

const TIE_LABELS: Record<keyof TieWeights, string> = {
    follow: 'Follow',
    suggested: 'Suggested',
    like: 'Like',
    comment: 'Comment',
    tag: 'Tag',
};

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CommunityDetectionPage() {
    // Kernel
    const [kernelAccounts, setKernelAccounts] = useState<SearchResult[]>([]);

    // Kernel search
    const [kernelSearchTerm, setKernelSearchTerm] = useState('');
    const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const searchAbortRef = useRef<AbortController | null>(null);
    const searchBoxRef = useRef<HTMLDivElement | null>(null);
    const [searchFocused, setSearchFocused] = useState(false);

    // Weights
    const [weights, setWeights] = useState<TieWeights>({...DEFAULT_TIE_WEIGHTS});
    const [weightsOpen, setWeightsOpen] = useState(false);

    // Candidates
    const [candidates, setCandidates] = useState<CandidateAccount[]>([]);
    const [isComputing, setIsComputing] = useState(false);
    const [hasRun, setHasRun] = useState(false);

    // Excluded accounts
    const [excludedAccounts, setExcludedAccounts] = useState<CandidateAccount[]>([]);
    const [excludedOpen, setExcludedOpen] = useState(false);

    // Derived
    const kernelIds = kernelAccounts.map(a => a.id);
    const kernelIdSet = new Set(kernelIds);
    const excludedIds = excludedAccounts.map(a => a.id);
    const excludedIdSet = new Set(excludedIds);
    const visibleCandidates = candidates.filter(c => !excludedIdSet.has(c.id));
    const hasVerifiedVisible = visibleCandidates.some(c => c.is_verified === true);

    useEffect(() => {
        document.title = 'Community Detection | Browsing Platform';
        return () => { searchAbortRef.current?.abort(); };
    }, []);

    // ── Kernel search ─────────────────────────────────────────────────────────

    const runKernelSearch = useCallback((term: string) => {
        if (!term.trim()) {
            setSearchResults([]);
            return;
        }
        if (searchAbortRef.current) searchAbortRef.current.abort();
        const controller = new AbortController();
        searchAbortRef.current = controller;
        setIsSearching(true);
        searchData(
            {search_mode: 'accounts', search_term: term, page_number: 1, page_size: 20, advanced_filters: null},
            {signal: controller.signal}
        ).then(results => {
            setSearchResults(results);
            setIsSearching(false);
        }).catch((e: any) => {
            if (e.name !== 'AbortError') setIsSearching(false);
        });
    }, []);

    useEffect(() => {
        const t = setTimeout(() => runKernelSearch(kernelSearchTerm), 300);
        return () => clearTimeout(t);
    }, [kernelSearchTerm, runKernelSearch]);

    const addToKernel = (result: SearchResult) => {
        if (kernelIdSet.has(result.id)) return;
        setKernelAccounts(prev => [...prev, result]);
        setKernelSearchTerm('');
        setSearchResults([]);
    };

    const removeFromKernel = (id: number) => {
        setKernelAccounts(prev => prev.filter(a => a.id !== id));
    };

    // ── Candidates ────────────────────────────────────────────────────────────

    const runAnalysis = async () => {
        setIsComputing(true);
        try {
            const resp: CommunityCandidatesResponse = await fetchCommunityCandidates(
                kernelIds, excludedIds, weights
            );
            setCandidates(resp.candidates);
            setHasRun(true);
        } finally {
            setIsComputing(false);
        }
    };

    const addCandidateToKernel = (candidate: CandidateAccount) => {
        const asResult: SearchResult = {
            id: candidate.id,
            page: 'account',
            title: candidateTitle(candidate),
            details: candidate.bio ?? undefined,
            thumbnails: candidate.thumbnails,
            metadata: {media_count: candidate.media_count},
        };
        addToKernel(asResult);
        setCandidates(prev => prev.filter(c => c.id !== candidate.id));
    };

    const excludeCandidate = (candidate: CandidateAccount) => {
        setExcludedAccounts(prev => [...prev, candidate]);
    };

    const restoreCandidate = (id: number) => {
        setExcludedAccounts(prev => prev.filter(a => a.id !== id));
    };

    const autoRemoveVerified = () => {
        const verified = visibleCandidates.filter(c => c.is_verified === true);
        setExcludedAccounts(prev => [...prev, ...verified]);
    };

    // ── Close search dropdown on outside click ────────────────────────────────

    useEffect(() => {
        const handleClick = (e: MouseEvent) => {
            if (searchBoxRef.current && !searchBoxRef.current.contains(e.target as Node)) {
                setSearchFocused(false);
            }
        };
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, []);

    const showDropdown = searchFocused && (isSearching || searchResults.length > 0);
    const filteredResults = searchResults.filter(r => !kernelIdSet.has(r.id));

    // ── Render ────────────────────────────────────────────────────────────────

    return (
        <div className="page-wrap">
            <TopNavBar>Community Detection</TopNavBar>
            <div className="page-content content-wrap">
                <Stack gap={3} divider={<Divider orientation="horizontal" flexItem/>}>

                    {/* ── Kernel section ───────────────────────────────────── */}
                    <Box>
                        <Typography variant="h6" gutterBottom>Kernel (Seed Set)</Typography>
                        <Box ref={searchBoxRef} sx={{position: 'relative', maxWidth: 480}}>
                            <OutlinedInput
                                value={kernelSearchTerm}
                                onChange={e => setKernelSearchTerm(e.target.value)}
                                onFocus={() => setSearchFocused(true)}
                                placeholder="Search accounts to add to kernel…"
                                size="small"
                                fullWidth
                                startAdornment={
                                    isSearching
                                        ? <CircularProgress size={16} sx={{mr: 1}}/>
                                        : <SearchIcon fontSize="small" sx={{mr: 0.5, color: 'text.disabled'}}/>
                                }
                            />
                            {showDropdown && (
                                <Paper
                                    elevation={4}
                                    sx={{
                                        position: 'absolute',
                                        top: '100%',
                                        left: 0,
                                        right: 0,
                                        zIndex: 10,
                                        maxHeight: 260,
                                        overflowY: 'auto',
                                        mt: 0.5,
                                    }}
                                >
                                    {isSearching && filteredResults.length === 0 && (
                                        <Box sx={{p: 1.5}}>
                                            <CircularProgress size={16}/>
                                        </Box>
                                    )}
                                    {!isSearching && filteredResults.length === 0 && (
                                        <Box sx={{p: 1.5}}>
                                            <Typography variant="body2" color="text.secondary">
                                                No results
                                            </Typography>
                                        </Box>
                                    )}
                                    <List dense disablePadding>
                                        {filteredResults.map(result => (
                                            <ListItemButton
                                                key={result.id}
                                                onClick={() => addToKernel(result)}
                                            >
                                                <ListItemText
                                                    primary={result.title}
                                                    secondary={result.details || undefined}
                                                    primaryTypographyProps={{noWrap: true}}
                                                    secondaryTypographyProps={{noWrap: true}}
                                                />
                                            </ListItemButton>
                                        ))}
                                    </List>
                                </Paper>
                            )}
                        </Box>

                        {kernelAccounts.length > 0 && (
                            <Stack direction="row" flexWrap="wrap" gap={1} sx={{mt: 1.5}}>
                                {kernelAccounts.map(acct => (
                                    <Chip
                                        key={acct.id}
                                        label={acct.title}
                                        onDelete={() => removeFromKernel(acct.id)}
                                        component="a"
                                        href={`/account/${acct.id}`}
                                        clickable
                                    />
                                ))}
                            </Stack>
                        )}
                    </Box>

                    {/* ── Weights section ──────────────────────────────────── */}
                    <Box>
                        <Button
                            variant="text"
                            size="small"
                            onClick={() => setWeightsOpen(p => !p)}
                            endIcon={
                                <ExpandMoreIcon
                                    sx={{
                                        transform: weightsOpen ? 'rotate(180deg)' : 'none',
                                        transition: 'transform 0.2s',
                                    }}
                                />
                            }
                        >
                            Tie Weights
                        </Button>
                        <Collapse in={weightsOpen} unmountOnExit>
                            <Stack direction="row" flexWrap="wrap" gap={2} sx={{mt: 1.5}}>
                                {(Object.keys(TIE_LABELS) as (keyof TieWeights)[]).map(tie => (
                                    <NumberField
                                        key={tie}
                                        label={TIE_LABELS[tie]}
                                        value={weights[tie]}
                                        min={0}
                                        step={0.1}
                                        size="small"
                                        onValueChange={v =>
                                            setWeights(prev => ({...prev, [tie]: v ?? 0}))
                                        }
                                        sx={{width: 130}}
                                    />
                                ))}
                            </Stack>
                        </Collapse>
                    </Box>

                    {/* ── Run button ───────────────────────────────────────── */}
                    <Box>
                        <Tooltip
                            title={kernelIds.length === 0 ? 'Add at least one account to the kernel first' : ''}
                            disableHoverListener={kernelIds.length > 0}
                        >
                            <span>
                                <Button
                                    variant="contained"
                                    disabled={kernelIds.length === 0 || isComputing}
                                    onClick={runAnalysis}
                                    startIcon={
                                        isComputing
                                            ? <CircularProgress size={16} color="inherit"/>
                                            : <PlayArrowIcon/>
                                    }
                                >
                                    {isComputing ? 'Analyzing…' : (hasRun ? 'Re-run Detection' : 'Run Community Detection')}
                                </Button>
                            </span>
                        </Tooltip>
                    </Box>

                    {/* ── Candidates section ───────────────────────────────── */}
                    {hasRun && (
                        <Box>
                            <Stack
                                direction="row"
                                justifyContent="space-between"
                                alignItems="center"
                                sx={{mb: 1.5}}
                            >
                                <Typography variant="h6">
                                    Top Candidates ({visibleCandidates.length})
                                </Typography>
                                <Tooltip
                                    title={
                                        hasVerifiedVisible
                                            ? 'Exclude all verified accounts from results'
                                            : 'No verified accounts in current results'
                                    }
                                >
                                    <span>
                                        <Button
                                            variant="outlined"
                                            size="small"
                                            disabled={!hasVerifiedVisible}
                                            onClick={autoRemoveVerified}
                                        >
                                            Remove Verified Accounts
                                        </Button>
                                    </span>
                                </Tooltip>
                            </Stack>

                            {visibleCandidates.length === 0 ? (
                                <Typography color="text.secondary">
                                    {candidates.length > 0
                                        ? 'All candidates have been excluded.'
                                        : 'No candidates found. Try expanding the kernel or adjusting weights.'}
                                </Typography>
                            ) : (
                                <Stack spacing={1.5} divider={<Divider/>}>
                                    {visibleCandidates.map(candidate => (
                                        <CandidateCard
                                            key={candidate.id}
                                            candidate={candidate}
                                            onAddToKernel={() => addCandidateToKernel(candidate)}
                                            onExclude={() => excludeCandidate(candidate)}
                                        />
                                    ))}
                                </Stack>
                            )}
                        </Box>
                    )}

                    {/* ── Excluded accounts section ────────────────────────── */}
                    {excludedAccounts.length > 0 && (
                        <Box>
                            <Button
                                variant="text"
                                size="small"
                                onClick={() => setExcludedOpen(p => !p)}
                                endIcon={
                                    <ExpandMoreIcon
                                        sx={{
                                            transform: excludedOpen ? 'rotate(180deg)' : 'none',
                                            transition: 'transform 0.2s',
                                        }}
                                    />
                                }
                            >
                                Excluded Accounts ({excludedAccounts.length})
                            </Button>
                            <Collapse in={excludedOpen} unmountOnExit>
                                <Stack spacing={0.5} sx={{mt: 1}}>
                                    {excludedAccounts.map(acct => (
                                        <Stack
                                            key={acct.id}
                                            direction="row"
                                            alignItems="center"
                                            gap={1}
                                        >
                                            <Typography
                                                component="a"
                                                href={`/account/${acct.id}`}
                                                sx={{flex: 1, textDecoration: 'none', color: 'text.primary'}}
                                                noWrap
                                            >
                                                {candidateTitle(acct)}
                                            </Typography>
                                            <Button
                                                size="small"
                                                variant="text"
                                                onClick={() => restoreCandidate(acct.id)}
                                            >
                                                Restore
                                            </Button>
                                        </Stack>
                                    ))}
                                </Stack>
                            </Collapse>
                        </Box>
                    )}

                </Stack>
            </div>
        </div>
    );
}
