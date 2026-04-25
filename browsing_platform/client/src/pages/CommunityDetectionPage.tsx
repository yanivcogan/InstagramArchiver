import React, {useMemo, useState} from 'react';
import {
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Collapse,
    Divider,
    IconButton,
    Link,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
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
            borderColor: 'divider',
            borderRadius: 4,
            px: 1,
            py: 0.25,
            bgcolor: 'background.paper',
        }}>
            <Link href={`/account/${account.id}`} underline="hover" color="text.primary"
                  sx={{fontSize: '0.875rem', lineHeight: 1.5}}>
                {account.title}
            </Link>
            <IconButton size="small" onClick={onRemove}
                        sx={{p: 0.25, ml: 0.25}} aria-label={`Remove ${account.title} from kernel`}>
                <CloseIcon sx={{fontSize: '0.875rem'}}/>
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
                        <SearchResultThumbnails thumbnails={candidate.thumbnails} totalCount={candidate.media_count}/>
                        <Stack direction="row" gap={0.75} flexWrap="wrap" sx={{mt: 0.75}}>
                            <Chip
                                label={`Score: ${candidate.score % 1 === 0 ? candidate.score : candidate.score.toFixed(2)}`}
                                size="small" color="primary" variant="outlined"
                            />
                            <Chip
                                label={`${candidate.kernel_connections} kernel connection${candidate.kernel_connections !== 1 ? 's' : ''}`}
                                size="small" variant="outlined"
                            />
                            {candidate.is_verified && (
                                <Chip label="Verified" size="small" color="info" variant="outlined"/>
                            )}
                        </Stack>
                    </Box>
                    <Stack direction="column" gap={1} sx={{flexShrink: 0}}>
                        <Button size="small" variant="outlined" onClick={onAddToKernel}>Add to Kernel</Button>
                        <Button size="small" variant="outlined" color="warning" onClick={onExclude}>Exclude</Button>
                    </Stack>
                </Stack>
            </CardContent>
        </Card>
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
                <Stack gap={3} divider={<Divider orientation="horizontal" flexItem/>}>

                    {/* ── Kernel section ───────────────────────────────────── */}
                    <Box>
                        <Typography variant="h6" gutterBottom>Kernel (Seed Set)</Typography>

                        <SearchPanel
                            query={KERNEL_SEARCH_QUERY}
                            onSearch={() => {}}
                            autoSearch={300}
                            showModeSelector={false}
                            showAdvancedFilters={false}
                            showTaggingMode={false}
                            onResultClick={(result) => {
                                if (!kernelIdSet.has(result.id)) addToKernel(result);
                            }}
                        />

                        {kernelAccounts.length > 0 && (
                            <Stack direction="row" flexWrap="wrap" gap={1} sx={{mt: 2}}>
                                {kernelAccounts.map(acct => (
                                    <KernelAccountPill
                                        key={acct.id}
                                        account={acct}
                                        onRemove={() => removeFromKernel(acct.id)}
                                    />
                                ))}
                            </Stack>
                        )}
                    </Box>

                    {/* ── Weights section ──────────────────────────────────── */}
                    <Box>
                        <Button variant="text" size="small" onClick={() => setWeightsOpen(p => !p)}
                                endIcon={<ExpandMoreIcon sx={{transform: weightsOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s'}}/>}>
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
                                        onValueChange={v => setWeights(prev => ({...prev, [tie]: v ?? 0}))}
                                        sx={{width: 130}}
                                    />
                                ))}
                            </Stack>
                        </Collapse>
                    </Box>

                    {/* ── Run button ───────────────────────────────────────── */}
                    <Box>
                        <Tooltip title={kernelIds.length === 0 ? 'Add at least one account to the kernel first' : ''}
                                 disableHoverListener={kernelIds.length > 0}>
                            <span>
                                <Button variant="contained" disabled={kernelIds.length === 0 || isComputing}
                                        onClick={runAnalysis}
                                        startIcon={isComputing ? <CircularProgress size={16} color="inherit"/> : <PlayArrowIcon/>}>
                                    {isComputing ? 'Analyzing…' : (hasRun ? 'Re-run Detection' : 'Run Community Detection')}
                                </Button>
                            </span>
                        </Tooltip>
                    </Box>

                    {/* ── Candidates section ───────────────────────────────── */}
                    {hasRun && (
                        <Box>
                            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{mb: 1.5}}>
                                <Typography variant="h6">Top Candidates ({visibleCandidates.length})</Typography>
                                <Tooltip title={hasVerifiedVisible ? 'Exclude all verified accounts from results' : 'No verified accounts in current results'}>
                                    <span>
                                        <Button variant="outlined" size="small" disabled={!hasVerifiedVisible}
                                                onClick={autoRemoveVerified}>
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
                            <Button variant="text" size="small" onClick={() => setExcludedOpen(p => !p)}
                                    endIcon={<ExpandMoreIcon sx={{transform: excludedOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s'}}/>}>
                                Excluded Accounts ({excludedAccounts.length})
                            </Button>
                            <Collapse in={excludedOpen} unmountOnExit>
                                <Stack spacing={0.5} sx={{mt: 1}}>
                                    {excludedAccounts.map(acct => (
                                        <Stack key={acct.id} direction="row" alignItems="center" gap={1}>
                                            <Typography component="a" href={`/account/${acct.id}`}
                                                        sx={{flex: 1, textDecoration: 'none', color: 'text.primary'}} noWrap>
                                                {candidateTitle(acct)}
                                            </Typography>
                                            <Button size="small" variant="text" onClick={() => restoreCandidate(acct.id)}>
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
