import React, {useMemo, useState} from 'react';
import {
    Box,
    Button,
    Chip,
    CircularProgress,
    Collapse,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    IconButton,
    Link,
    Paper,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CloseIcon from '@mui/icons-material/Close';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import TopNavBar from '../UIComponents/TopNavBar/TopNavBar';
import {SearchResultThumbnails} from '../UIComponents/SearchResults/SearchResultParts';
import NumberField from '../UIComponents/MUINumberField/NumberField';
import SearchPanel from '../UIComponents/Search/SearchPanel';
import {
    CandidateAccount,
    CommunityCandidatesResponse,
    DEFAULT_TIE_WEIGHTS,
    fetchCommunityCandidates,
    ISearchQuery,
    SearchResult,
    TieWeights,
} from '../services/DataFetcher';

function candidateTitle(c: Pick<CandidateAccount, 'id' | 'url_suffix' | 'display_name'>): string {
    return c.display_name
        ? `${c.url_suffix} (${c.display_name})`
        : (c.url_suffix ?? `Account ${c.id}`);
}

// ── Step badge ────────────────────────────────────────────────────────────────

function StepBadge({n, active}: {n: number; active?: boolean}) {
    return (
        <Box sx={{
            width: 24, height: 24, borderRadius: '50%',
            border: '2px solid',
            borderColor: active ? 'primary.main' : 'divider',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
            bgcolor: active ? 'primary.main' : 'transparent',
            transition: 'all 0.2s',
        }}>
            <Typography sx={{
                fontSize: '0.7rem', fontWeight: 700, lineHeight: 1,
                color: active ? 'primary.contrastText' : 'text.disabled',
            }}>
                {n}
            </Typography>
        </Box>
    );
}

// ── Section header ────────────────────────────────────────────────────────────

interface SectionHeaderProps {
    step: number;
    title: string;
    active?: boolean;
    action?: React.ReactNode;
}

function SectionHeader({step, title, active, action}: SectionHeaderProps) {
    return (
        <Stack direction="row" alignItems="center" gap={1.25} sx={{mb: 1.5}}>
            <StepBadge n={step} active={active}/>
            <Typography variant="subtitle1" sx={{fontWeight: 600, flex: 1, letterSpacing: '-0.01em'}}>
                {title}
            </Typography>
            {action}
        </Stack>
    );
}

// ── Kernel account pill ───────────────────────────────────────────────────────

interface KernelAccountPillProps {
    account: SearchResult;
    onRemove: () => void;
}

function KernelAccountPill({account, onRemove}: KernelAccountPillProps) {
    return (
        <Box sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0.5,
            border: '1px solid',
            borderColor: 'primary.light',
            borderRadius: 4,
            px: 1, py: 0.25,
            bgcolor: 'background.paper',
            '&:hover': {borderColor: 'primary.main'},
            transition: 'border-color 0.15s',
        }}>
            <Link href={`/account/${account.id}`} underline="hover" color="primary.main"
                  sx={{fontSize: '0.8125rem', lineHeight: 1.5, fontWeight: 500}}>
                {account.title}
            </Link>
            <IconButton size="small" onClick={onRemove}
                        sx={{p: 0.25, ml: 0.25, color: 'primary.light', '&:hover': {color: 'error.main'}}}
                        aria-label={`Remove ${account.title} from kernel`}>
                <CloseIcon sx={{fontSize: '0.8rem'}}/>
            </IconButton>
        </Box>
    );
}

// ── Candidate card ────────────────────────────────────────────────────────────

interface CandidateCardProps {
    candidate: CandidateAccount;
    onAddToKernel: () => void;
    onExclude: () => void;
}

function CandidateCard({candidate, onAddToKernel, onExclude}: CandidateCardProps) {
    const title = candidateTitle(candidate);
    const score = candidate.score % 1 === 0
        ? candidate.score.toString()
        : candidate.score.toFixed(2);
    return (
        <Stack direction="row" gap={2} alignItems="flex-start" sx={{py: 0.5}}>
            {/* Score column */}
            <Box sx={{
                flexShrink: 0, width: 56, textAlign: 'center',
                pt: 0.5, borderRight: '1px solid', borderColor: 'divider', pr: 2,
            }}>
                <Typography variant="h5" sx={{fontWeight: 700, lineHeight: 1, color: 'primary.main', fontSize: '1.5rem'}}>
                    {score}
                </Typography>
                <Typography variant="caption" sx={{color: 'text.disabled', display: 'block', mt: 0.25, letterSpacing: '0.05em', textTransform: 'uppercase', fontSize: '0.6rem'}}>
                    score
                </Typography>
                <Box sx={{mt: 1}}>
                    <Typography variant="body2" sx={{fontWeight: 600, lineHeight: 1, color: 'text.secondary'}}>
                        {candidate.kernel_connections}
                    </Typography>
                    <Typography variant="caption" sx={{color: 'text.disabled', fontSize: '0.6rem', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
                        conn.
                    </Typography>
                </Box>
            </Box>

            {/* Content */}
            <Box sx={{flex: 1, minWidth: 0}}>
                <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap">
                    <a href={`/account/${candidate.id}`} style={{textDecoration: 'none', color: 'inherit'}}>
                        <Typography variant="subtitle1" sx={{fontWeight: 600, wordBreak: 'break-word', '&:hover': {textDecoration: 'underline'}}}>
                            {title}
                        </Typography>
                    </a>
                    {candidate.is_verified && (
                        <Chip label="Verified" size="small" color="info" variant="outlined"
                              sx={{height: 18, '& .MuiChip-label': {px: 0.75, fontSize: '0.6rem'}}}/>
                    )}
                </Stack>
                {candidate.bio && (
                    <Typography variant="body2" color="text.secondary" sx={{mt: 0.25, fontSize: '0.8125rem'}}>
                        {candidate.bio}
                    </Typography>
                )}
                <SearchResultThumbnails thumbnails={candidate.thumbnails} totalCount={candidate.media_count}/>
            </Box>

            {/* Actions */}
            <Stack direction="column" gap={0.5} sx={{flexShrink: 0}}>
                <Button size="small" variant="outlined" onClick={onAddToKernel}
                        sx={{whiteSpace: 'nowrap', fontSize: '0.75rem'}}>
                    Add to Kernel
                </Button>
                <Button size="small" variant="text" color="warning" onClick={onExclude}
                        sx={{fontSize: '0.75rem'}}>
                    Exclude
                </Button>
            </Stack>
        </Stack>
    );
}

// ── Tie weight labels ─────────────────────────────────────────────────────────

const TIE_LABELS: Record<keyof TieWeights, string> = {
    follow: 'Follow', suggested: 'Suggested', like: 'Like', comment: 'Comment', tag: 'Tag',
};

const KERNEL_SEARCH_QUERY: ISearchQuery = {
    search_mode: 'accounts',
    search_term: '',
    page_number: 1,
    page_size: 20,
    advanced_filters: null,
    tag_ids: [],
    tag_filter_mode: 'any',
};

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CommunityDetectionPage() {
    // Kernel
    const [kernelAccounts, setKernelAccounts] = useState<SearchResult[]>([]);
    const [kernelModalOpen, setKernelModalOpen] = useState(false);

    // Weights
    const [weights, setWeights] = useState<TieWeights>({...DEFAULT_TIE_WEIGHTS});

    // Candidates
    const [candidates, setCandidates] = useState<CandidateAccount[]>([]);
    const [isComputing, setIsComputing] = useState(false);
    const [hasRun, setHasRun] = useState(false);

    // Excluded accounts
    const [excludedAccounts, setExcludedAccounts] = useState<CandidateAccount[]>([]);
    const [excludedOpen, setExcludedOpen] = useState(false);

    // Derived
    const kernelIds = useMemo(() => kernelAccounts.map(a => a.id), [kernelAccounts]);
    const kernelIdSet = useMemo(() => new Set(kernelIds), [kernelIds]);
    const excludedIds = useMemo(() => excludedAccounts.map(a => a.id), [excludedAccounts]);
    const excludedIdSet = useMemo(() => new Set(excludedIds), [excludedIds]);
    const visibleCandidates = useMemo(() => candidates.filter(c => !excludedIdSet.has(c.id)), [candidates, excludedIdSet]);
    const hasVerifiedVisible = useMemo(() => visibleCandidates.some(c => c.is_verified === true), [visibleCandidates]);

    React.useEffect(() => {
        document.title = 'Community Detection | Browsing Platform';
    }, []);

    // ── Kernel management ─────────────────────────────────────────────────────

    const addToKernel = (result: SearchResult) => {
        if (kernelIdSet.has(result.id)) return;
        setKernelAccounts(prev => [...prev, result]);
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
        addToKernel({
            id: candidate.id,
            page: 'account',
            title: candidateTitle(candidate),
            details: candidate.bio ?? undefined,
            thumbnails: candidate.thumbnails,
            metadata: {media_count: candidate.media_count},
        });
        setCandidates(prev => prev.filter(c => c.id !== candidate.id));
    };

    const excludeCandidate = (candidate: CandidateAccount) => {
        setExcludedAccounts(prev => [...prev, candidate]);
    };

    const restoreCandidate = (id: number) => {
        setExcludedAccounts(prev => prev.filter(a => a.id !== id));
    };

    const autoRemoveVerified = () => {
        setExcludedAccounts(prev => [...prev, ...visibleCandidates.filter(c => c.is_verified === true)]);
    };

    // ── Render ────────────────────────────────────────────────────────────────

    return (
        <div className="page-wrap">
            <TopNavBar>Community Detection</TopNavBar>
            <div className="page-content content-wrap">

                {/* ── Kernel modal ─────────────────────────────────────────── */}
                <Dialog open={kernelModalOpen} onClose={() => setKernelModalOpen(false)}
                        maxWidth="sm" fullWidth>
                    <DialogTitle sx={{pr: 6}}>
                        Add Accounts to Kernel
                        <IconButton onClick={() => setKernelModalOpen(false)} size="small"
                                    sx={{position: 'absolute', right: 8, top: 8}}>
                            <CloseIcon/>
                        </IconButton>
                    </DialogTitle>
                    <DialogContent dividers sx={{p: 2}}>
                        <SearchPanel
                            query={KERNEL_SEARCH_QUERY}
                            onSearch={() => {}}
                            autoSearch={300}
                            showModeSelector={false}
                            showAdvancedFilters={false}
                            showTaggingMode={false}
                            checkedIds={kernelIdSet}
                            onToggleChecked={(result) => {
                                if (kernelIdSet.has(result.id)) removeFromKernel(result.id);
                                else addToKernel(result);
                            }}
                        />
                    </DialogContent>
                    <DialogActions>
                        <Typography variant="body2" color="text.secondary" sx={{flex: 1, pl: 1}}>
                            {kernelAccounts.length} account{kernelAccounts.length !== 1 ? 's' : ''} in kernel
                        </Typography>
                        <Button variant="contained" onClick={() => setKernelModalOpen(false)}>Done</Button>
                    </DialogActions>
                </Dialog>

                <Stack gap={0}>

                    {/* ── Step 1: Kernel ───────────────────────────────────── */}
                    <Paper variant="outlined" sx={{p: 2.5, borderRadius: 2}}>
                        <SectionHeader
                            step={1}
                            title="Kernel — Seed Accounts"
                            active={kernelAccounts.length > 0}
                            action={
                                <Tooltip title="Search and add accounts">
                                    <Button
                                        size="small"
                                        variant={kernelAccounts.length === 0 ? 'contained' : 'outlined'}
                                        startIcon={<AddIcon/>}
                                        onClick={() => setKernelModalOpen(true)}
                                        sx={{flexShrink: 0}}
                                    >
                                        Add accounts
                                    </Button>
                                </Tooltip>
                            }
                        />

                        {kernelAccounts.length > 0 ? (
                            <Stack direction="row" flexWrap="wrap" gap={1}>
                                {kernelAccounts.map(acct => (
                                    <KernelAccountPill
                                        key={acct.id}
                                        account={acct}
                                        onRemove={() => removeFromKernel(acct.id)}
                                    />
                                ))}
                            </Stack>
                        ) : (
                            <Box
                                onClick={() => setKernelModalOpen(true)}
                                sx={{
                                    border: '1.5px dashed',
                                    borderColor: 'divider',
                                    borderRadius: 1.5,
                                    p: 2,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 1.5,
                                    cursor: 'pointer',
                                    color: 'text.secondary',
                                    '&:hover': {borderColor: 'primary.main', color: 'primary.main', bgcolor: 'action.hover'},
                                    transition: 'all 0.15s',
                                }}
                            >
                                <AddIcon sx={{fontSize: '1.1rem', flexShrink: 0}}/>
                                <Typography variant="body2">
                                    Add seed accounts to begin community detection
                                </Typography>
                            </Box>
                        )}
                    </Paper>

                    <Box sx={{width: 2, height: 16, bgcolor: 'divider', mx: 'auto'}}/>

                    {/* ── Step 2: Weights ──────────────────────────────────── */}
                    <Paper variant="outlined" sx={{p: 2.5, borderRadius: 2}}>
                        <SectionHeader
                            step={2}
                            title="Tie Weights"
                        />
                        <Stack direction="column" gap={1}>
                            <Typography variant="body2" color="text.secondary" sx={{mt: -0.5}}>
                                Adjust how different interaction types influence the strength of relation between accounts:
                            </Typography>
                            <Stack direction="row" flexWrap="wrap" gap={2} sx={{mt: 0.5}}>
                                {(Object.keys(TIE_LABELS) as (keyof TieWeights)[]).map(tie => (
                                    <NumberField
                                        key={tie}
                                        label={TIE_LABELS[tie]}
                                        value={weights[tie]}
                                        min={0}
                                        step={0.1}
                                        size="small"
                                        onValueChange={v => setWeights(prev => ({...prev, [tie]: v ?? 0}))}
                                        sx={{width: 130}}
                                    />
                                ))}
                            </Stack>
                        </Stack>
                    </Paper>

                    <Box sx={{width: 2, height: 16, bgcolor: 'divider', mx: 'auto'}}/>

                    {/* ── Step 3: Run ──────────────────────────────────────── */}
                    <Paper variant="outlined" sx={{p: 2.5, borderRadius: 2}}>
                        <SectionHeader step={3} title="Run Analysis"/>
                        <Tooltip
                            title={kernelIds.length === 0 ? 'Add at least one account to the kernel first' : ''}
                            disableHoverListener={kernelIds.length > 0}
                        >
                            <span>
                                <Button
                                    variant="contained"
                                    size="large"
                                    disabled={kernelIds.length === 0 || isComputing}
                                    onClick={runAnalysis}
                                    startIcon={isComputing ? <CircularProgress size={18} color="inherit"/> : <PlayArrowIcon/>}
                                    sx={{minWidth: 220}}
                                >
                                    {isComputing ? 'Analyzing…' : (hasRun ? 'Re-run Detection' : 'Run Community Detection')}
                                </Button>
                            </span>
                        </Tooltip>
                    </Paper>

                    {/* ── Candidates ───────────────────────────────────────── */}
                    {hasRun && (
                        <>
                            <Box sx={{display: 'flex', justifyContent: 'center'}}>
                                <Box sx={{width: '2px', height: 16, bgcolor: 'divider'}}/>
                            </Box>
                            <Paper variant="outlined" sx={{p: 2.5, borderRadius: 2}}>
                                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{mb: 1.5}}>
                                    <Typography variant="subtitle1" sx={{fontWeight: 600}}>
                                        Top Candidates
                                        {visibleCandidates.length > 0 && (
                                            <Typography component="span" variant="body2" color="text.secondary" sx={{ml: 1}}>
                                                {visibleCandidates.length} result{visibleCandidates.length !== 1 ? 's' : ''}
                                            </Typography>
                                        )}
                                    </Typography>
                                    <Tooltip title={hasVerifiedVisible ? 'Exclude all verified accounts from results' : 'No verified accounts in current results'}>
                                        <span>
                                            <Button variant="outlined" size="small" disabled={!hasVerifiedVisible}
                                                    onClick={autoRemoveVerified} sx={{flexShrink: 0}}>
                                                Remove Verified
                                            </Button>
                                        </span>
                                    </Tooltip>
                                </Stack>

                                {visibleCandidates.length === 0 ? (
                                    <Typography color="text.secondary" variant="body2">
                                        {candidates.length > 0
                                            ? 'All candidates have been excluded.'
                                            : 'No candidates found. Try expanding the kernel or adjusting weights.'}
                                    </Typography>
                                ) : (
                                    <Stack spacing={0} divider={<Divider/>}>
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
                            </Paper>
                        </>
                    )}

                    {/* ── Excluded accounts ────────────────────────────────── */}
                    {excludedAccounts.length > 0 && (
                        <>
                            <Box sx={{height: 8}}/>
                            <Box>
                                <Button
                                    variant="text" size="small"
                                    onClick={() => setExcludedOpen(p => !p)}
                                    endIcon={<ExpandMoreIcon sx={{transform: excludedOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s'}}/>}
                                    sx={{color: 'text.secondary'}}
                                >
                                    Excluded ({excludedAccounts.length})
                                </Button>
                                <Collapse in={excludedOpen} unmountOnExit>
                                    <Stack spacing={0.25} sx={{mt: 0.5, pl: 0.5}}>
                                        {excludedAccounts.map(acct => (
                                            <Stack key={acct.id} direction="row" alignItems="center" gap={1}
                                                   sx={{py: 0.25}}>
                                                <Typography
                                                    component="a" href={`/account/${acct.id}`}
                                                    sx={{flex: 1, textDecoration: 'none', color: 'text.disabled', fontSize: '0.8125rem'}}
                                                    noWrap
                                                >
                                                    {candidateTitle(acct)}
                                                </Typography>
                                                <Button size="small" variant="text" onClick={() => restoreCandidate(acct.id)}
                                                        sx={{flexShrink: 0, fontSize: '0.75rem', color: 'text.secondary'}}>
                                                    Restore
                                                </Button>
                                            </Stack>
                                        ))}
                                    </Stack>
                                </Collapse>
                            </Box>
                        </>
                    )}

                </Stack>
            </div>
        </div>
    );
}
