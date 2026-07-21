import React, {useEffect, useMemo, useRef, useState} from 'react';
import {useSearchParams} from 'react-router';
import {
    Alert,
    Box,
    Button,
    Checkbox,
    Chip,
    CircularProgress,
    Collapse,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    FormControlLabel,
    IconButton,
    Link,
    Pagination,
    Paper,
    Skeleton,
    Snackbar,
    Stack,
    TextField,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CloseIcon from '@mui/icons-material/Close';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import AutoModeIcon from '@mui/icons-material/AutoMode';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import FileUploadOutlinedIcon from '@mui/icons-material/FileUploadOutlined';
import UndoIcon from '@mui/icons-material/Undo';
import ViewListIcon from '@mui/icons-material/ViewList';
import ViewAgendaIcon from '@mui/icons-material/ViewAgenda';
import TopNavBar from '../UIComponents/TopNavBar/TopNavBar';
import AccountBlock from '../UIComponents/CommunityDetection/AccountBlock';
import AccountDisplayFilters, {
    DEFAULT_DISPLAY_FILTERS,
    DisplayFilters,
    isDisplayFilterActive,
} from '../UIComponents/CommunityDetection/AccountDisplayFilters';
import NumberField from '../UIComponents/MUINumberField/NumberField';
import SearchPanel from '../UIComponents/Search/SearchPanel';
import QuickAccessTypeDropdown from '../UIComponents/Tags/QuickAccessTypeDropdown';
import TagSelector from '../UIComponents/Tags/TagSelector';
import {
    batchAnnotate,
    CandidateAccount,
    CommunityCandidatesResponse,
    DEFAULT_TIE_WEIGHTS,
    DismissedAccount,
    fetchCommunityCandidates,
    fetchKernelDetails,
    fetchRelatedTagStats,
    fetchTagKernelAccounts,
    fetchTagsForSearchResults,
    ISearchQuery,
    removeAccountTag,
    saveTagDismissals,
    SearchResult,
    TagKernelAccount,
    TagKernelResponse,
    Thumbnail,
    TieWeights,
} from '../services/DataFetcher';
import {IQuickAccessTypeDropdown, ITagStat, ITagWithType} from '../types/tags';
import {outboundStatus} from '../UIComponents/Entities/ArchiverAccessList';
import {useCanViewArchiverAccess} from '../services/archiverAccessPermission';
import {downloadTextFile} from '../services/utils';

const EMPTY_ID_SET = new Set<number>();
const COMMUNITY_TAG_PLACEHOLDER = 'Assign Community Tag';
const BASE_TITLE = 'Community Detection | Browsing Platform';
const COMMUNITY_TAG_PARAM = 'communityTag';
const KERNEL_PAGE_SIZE = 20;
// Redacts fields that must not go into an exported/downloadable state file:
// thumbnails (bulk) and archiver_access (archiver identities are sensitive).
// This is the serialization boundary — route every exported account row through
// it. undefined keys are omitted by JSON.stringify.
const sanitizeForExport = <T extends { thumbnails?: Thumbnail[] }>(obj: T): T =>
    ({...obj, thumbnails: [], archiver_access: undefined} as T);

// ── Serialisable state (export / import) ──────────────────────────────────────

interface CommunityStateExport {
    version: 1;
    community_tag: ITagWithType | null;
    community_dropdown: IQuickAccessTypeDropdown | null;
    kernel: Array<{ account: SearchResult; manuallyAdded: boolean; tagSources: ITagWithType[] }>;
    weights: TieWeights;
    excluded: CandidateAccount[];
}

function isCommunityStateExport(v: unknown): v is CommunityStateExport {
    if (!v || typeof v !== 'object') return false;
    const s = v as Record<string, unknown>;
    return s.version === 1
        && Array.isArray(s.kernel)
        && s.weights !== null && typeof s.weights === 'object'
        && Array.isArray(s.excluded);
}

// ── Kernel entry type ─────────────────────────────────────────────────────────

interface KernelEntry {
    account: SearchResult;
    manuallyAdded: boolean;
    tagSources: ITagWithType[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function candidateTitle(c: Pick<CandidateAccount, 'id' | 'url_suffix' | 'display_name'>): string {
    return c.display_name
        ? `${c.url_suffix} (${c.display_name})`
        : (c.url_suffix ?? `Account ${c.id}`);
}

// A persisted dismissal carries only the fields needed to render its chip and
// filter it out of the candidates list; the rest of CandidateAccount defaults
// to zero/null (these accounts are dismissed, so their stats are never shown).
function dismissedToCandidate(d: DismissedAccount): CandidateAccount {
    return {
        id: d.id,
        url_suffix: d.url_suffix,
        display_name: d.display_name,
        bio: null,
        is_verified: null,
        score: 0,
        kernel_connections: 0,
        thumbnails: [],
        media_count: 0,
        follower_count: 0,
        following_count: 0,
        post_count: 0,
    };
}

function candidateToDismissed(c: CandidateAccount): DismissedAccount {
    return {id: c.id, url_suffix: c.url_suffix, display_name: c.display_name};
}

function tagKernelAccountToSearchResult(a: TagKernelAccount): SearchResult {
    return {
        id: a.id,
        page: 'account',
        title: candidateTitle(a),
        details: a.bio ?? undefined,
        thumbnails: a.thumbnails,
        metadata: {media_count: a.media_count, url_suffix: a.url_suffix, display_name: a.display_name},
    };
}

// Display-filter predicate (true => hidden). Operates on per-account scraped
// relation / post counts. The candidates list and the seeds expanded view each
// pass their own independent filter state.
function isHiddenByFilters(
    c: Pick<CandidateAccount, 'follower_count' | 'following_count' | 'post_count' | 'archiver_access'>,
    filters: DisplayFilters,
): boolean {
    const relations = c.follower_count + c.following_count;
    if (filters.relationsMode === 'over' && !(relations > filters.relationsThreshold)) return true;
    if (filters.relationsMode === 'under' && !(relations < filters.relationsThreshold)) return true;
    if (filters.postsMode === 'has' && !(c.post_count >= 1)) return true;
    if (filters.postsMode === 'none' && !(c.post_count === 0)) return true;
    if (filters.archiverMode !== 'all') {
        const access = c.archiver_access ?? [];
        const isFollowed = access.some(e => outboundStatus(e) === 'following');
        switch (filters.archiverMode) {
            case 'followed_by_any':
                if (!isFollowed) return true;
                break;
            case 'followed_by':
                // A null label means no archiver has been picked yet — treat as
                // no constraint (show all) rather than hiding everything.
                if (filters.archiverLabel &&
                    !access.some(e => e.label === filters.archiverLabel && outboundStatus(e) === 'following'))
                    return true;
                break;
            case 'not_followed':
                if (isFollowed) return true;
                break;
            case 'not_followed_or_requested':
                if (isFollowed || access.some(e => outboundStatus(e) === 'requested')) return true;
                break;
        }
    }
    return false;
}

// ── Step badge ────────────────────────────────────────────────────────────────

function StepBadge({n, active}: { n: number; active?: boolean }) {
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
    entry: KernelEntry;
    communityDropdown: IQuickAccessTypeDropdown | null;
    onRemove: () => void;
    onTagToggle: (tag: ITagWithType) => void;
}

function KernelAccountPill({entry, communityDropdown, onRemove, onTagToggle}: KernelAccountPillProps) {
    const assignedTagIds = useMemo(
        () => new Set(entry.tagSources.map(t => t.id!)),
        [entry.tagSources],
    );

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
            flexWrap: 'wrap',
            '&:hover': {borderColor: 'primary.main'},
            transition: 'border-color 0.15s',
        }}>
            <Link href={`/account/${entry.account.id}`} target="_blank" rel="noopener noreferrer"
                  underline="hover" color="primary.main"
                  sx={{fontSize: '0.8125rem', lineHeight: 1.5, fontWeight: 500}}>
                {entry.account.title}
            </Link>

            {/* Tag membership indicator / control */}
            {communityDropdown && (
                <QuickAccessTypeDropdown
                    dropdown={communityDropdown}
                    assignedTagIds={assignedTagIds}
                    onSelect={onTagToggle}
                    placeholder={COMMUNITY_TAG_PLACEHOLDER}
                />
            )}

            {/* Manual indicator: shown when in tag mode but no tag sources */}
            {communityDropdown && entry.tagSources.length === 0 && entry.manuallyAdded && (
                <Chip
                    label="Manual"
                    size="small"
                    variant="outlined"
                    sx={{height: 18, fontSize: '0.6rem', '& .MuiChip-label': {px: 0.75}}}
                />
            )}

            <IconButton size="small" onClick={onRemove}
                        sx={{p: 0.25, ml: 0.25, color: 'primary.light', '&:hover': {color: 'error.main'}}}
                        aria-label={`Remove ${entry.account.title} from seeds`}>
                <CloseIcon sx={{fontSize: '0.8rem'}}/>
            </IconButton>
        </Box>
    );
}

// ── Candidate card ────────────────────────────────────────────────────────────

interface CandidateCardProps {
    candidate: CandidateAccount;
    communityDropdown: IQuickAccessTypeDropdown | null;
    assignedCommunityTagIds: Set<number>;
    onAddToKernel: () => void;
    onExclude: () => void;
    onTagToggle: (tag: ITagWithType) => void;
    tagDistribution?: ITagStat[];
    tagDistributionLoading: boolean;
    onTagDistributionOpen: () => void;
}

function CandidateCard({
                           candidate,
                           communityDropdown,
                           assignedCommunityTagIds,
                           onAddToKernel,
                           onExclude,
                           onTagToggle,
                           tagDistribution,
                           tagDistributionLoading,
                           onTagDistributionOpen,
                       }: CandidateCardProps) {
    return (
        <AccountBlock
            id={candidate.id}
            title={candidateTitle(candidate)}
            bio={candidate.bio}
            isVerified={candidate.is_verified}
            thumbnails={candidate.thumbnails}
            mediaCount={candidate.media_count}
            followerCount={candidate.follower_count}
            followingCount={candidate.following_count}
            postCount={candidate.post_count}
            score={candidate.score}
            kernelConnections={candidate.kernel_connections}
            archiverAccess={candidate.archiver_access}
            tagDistribution={tagDistribution}
            tagDistributionLoading={tagDistributionLoading}
            onTagDistributionOpen={onTagDistributionOpen}
            actions={
                <>
                    {communityDropdown ? (
                        <>
                            <Typography
                                variant="caption"
                                sx={{
                                    color: 'text.disabled',
                                    fontSize: '0.6rem',
                                    letterSpacing: '0.08em',
                                    textTransform: 'uppercase',
                                    lineHeight: 1,
                                }}
                            >
                                Tag &amp; add to seeds
                            </Typography>
                            <QuickAccessTypeDropdown
                                dropdown={communityDropdown}
                                assignedTagIds={assignedCommunityTagIds}
                                onSelect={onTagToggle}
                                placeholder={COMMUNITY_TAG_PLACEHOLDER}
                                emphasized
                            />
                            <Divider flexItem sx={{my: 0.25}}>
                                <Typography variant="caption" color="text.disabled" sx={{fontSize: '0.65rem'}}>
                                    or
                                </Typography>
                            </Divider>
                            <Button
                                size="small" variant="text" color="inherit"
                                onClick={onAddToKernel}
                                sx={{whiteSpace: 'nowrap', fontSize: '0.75rem', color: 'text.secondary'}}
                            >
                                Add without tag
                            </Button>
                        </>
                    ) : (
                        <Button
                            size="small" variant="contained"
                            onClick={onAddToKernel}
                            sx={{whiteSpace: 'nowrap', fontSize: '0.75rem'}}
                        >
                            Add to seeds
                        </Button>
                    )}
                    <Button
                        size="small" variant="text" color="error"
                        onClick={onExclude}
                        sx={{fontSize: '0.75rem'}}
                    >
                        Dismiss
                    </Button>
                </>
            }
        />
    );
}

// ── Kernel account card (expanded view) ───────────────────────────────────────

interface KernelAccountCardProps {
    entry: KernelEntry;
    detail?: CandidateAccount;
    loading: boolean;
    communityDropdown: IQuickAccessTypeDropdown | null;
    onStripAndRemove: () => void;
    onRemoveOnly: () => void;
    tagDistribution?: ITagStat[];
    tagDistributionLoading: boolean;
    onTagDistributionOpen: () => void;
}

function KernelAccountCard({
                               entry,
                               detail,
                               loading,
                               communityDropdown,
                               onStripAndRemove,
                               onRemoveOnly,
                               tagDistribution,
                               tagDistributionLoading,
                               onTagDistributionOpen,
                           }: KernelAccountCardProps) {
    const tagSources = entry.tagSources;
    const removesTags = !!communityDropdown && tagSources.length > 0;

    if (!detail && loading) {
        return (
            <Stack direction="row" gap={2} alignItems="center" sx={{py: 0.5}}>
                <Skeleton variant="rectangular" width={56} height={40}/>
                <Box sx={{flex: 1, minWidth: 0}}>
                    <Skeleton variant="text" width="40%"/>
                    <Skeleton variant="rectangular" height={100} sx={{mt: 1, maxWidth: 320}}/>
                </Box>
                <Skeleton variant="rectangular" width={148} height={32}/>
            </Stack>
        );
    }

    return (
        <AccountBlock
            id={entry.account.id}
            title={detail ? candidateTitle(detail) : entry.account.title}
            bio={detail?.bio}
            isVerified={detail?.is_verified}
            thumbnails={detail?.thumbnails ?? []}
            mediaCount={detail?.media_count ?? 0}
            followerCount={detail?.follower_count ?? 0}
            followingCount={detail?.following_count ?? 0}
            postCount={detail?.post_count ?? 0}
            score={detail?.score ?? 0}
            kernelConnections={detail?.kernel_connections ?? 0}
            archiverAccess={detail?.archiver_access}
            tagDistribution={tagDistribution}
            tagDistributionLoading={tagDistributionLoading}
            onTagDistributionOpen={onTagDistributionOpen}
            actions={
                removesTags ? (
                    <>
                        <Tooltip title="Also removes the community tag(s) from this account in the database">
                            <Button
                                size="small" variant="outlined" color="error"
                                onClick={onStripAndRemove}
                                sx={{fontSize: '0.75rem'}}
                            >
                                Remove &amp; strip tag(s)
                            </Button>
                        </Tooltip>
                        <Tooltip
                            title="Keeps the tag(s) — the account will return to the seeds the next time the community page is loaded for this tag">
                            <Button
                                size="small" variant="text" color="error"
                                onClick={onRemoveOnly}
                                sx={{fontSize: '0.75rem'}}
                            >
                                Remove from seeds
                            </Button>
                        </Tooltip>
                    </>
                ) : (
                    <Button
                        size="small" variant="outlined" color="error"
                        onClick={onRemoveOnly}
                        sx={{fontSize: '0.75rem'}}
                    >
                        Remove from seeds
                    </Button>
                )
            }
        />
    );
}

// ── Tie weight labels ─────────────────────────────────────────────────────────

// User-facing names for the tie types. "Tagged in posts" (not "Tag") — the
// bare word collides with the page's community-tag concept, which is unrelated.
const TIE_LABELS: Record<keyof TieWeights, string> = {
    follow: 'Follows',
    suggested: 'Suggested by Instagram',
    like: 'Likes',
    comment: 'Comments',
    tag: 'Tagged in posts',
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
    const [kernelEntries, setKernelEntries] = useState<KernelEntry[]>([]);
    const [kernelModalOpen, setKernelModalOpen] = useState(false);

    // Kernel display: compact pills vs. expanded rich blocks. Detail (scores,
    // thumbnails) for the expanded view is fetched on demand and is intentionally
    // NOT part of the exported state.
    const [kernelExpandedView, setKernelExpandedView] = useState(false);
    const [kernelDetails, setKernelDetails] = useState<Record<number, CandidateAccount>>({});
    const [kernelDetailsLoading, setKernelDetailsLoading] = useState(false);
    const [kernelPage, setKernelPage] = useState(1);

    // Confirmation before removing the community tag(s) that justify a kernel
    // member's inclusion and taking it out of the kernel (tag mode only).
    const [pendingKernelTagRemoval, setPendingKernelTagRemoval] = useState<KernelEntry | null>(null);

    // Display filters: visually hide entries by scraping state. The seeds list
    // (expanded view only) and the candidates list each have their own filter
    // state — filtering one list must never silently affect the other (or the
    // seeds CSV copy). Never exported.
    const [kernelFilters, setKernelFilters] = useState<DisplayFilters>(DEFAULT_DISPLAY_FILTERS);
    const [candidateFilters, setCandidateFilters] = useState<DisplayFilters>(DEFAULT_DISPLAY_FILTERS);

    // Whether this viewer may see archiver-access data (drives the access chips
    // and the archiver filter section). The server independently gates the data.
    const canViewArchiver = useCanViewArchiverAccess();

    // Community tag / tag mode
    const [communityTag, setCommunityTag] = useState<ITagWithType | null>(null);
    const [communityDropdown, setCommunityDropdown] = useState<IQuickAccessTypeDropdown | null>(null);

    // Tag transition modal (when user picks a community tag while kernel is non-empty)
    const [tagTransitionPending, setTagTransitionPending] = useState<{
        tag: ITagWithType;
        tagKernelAccounts: TagKernelAccount[];
        dropdown: IQuickAccessTypeDropdown;
        dismissals: DismissedAccount[];
    } | null>(null);
    const [tagTransitionApplyToExisting, setTagTransitionApplyToExisting] = useState(false);
    const [tagTransitionLoading, setTagTransitionLoading] = useState(false);

    // Confirmation for removing an untagged kernel account after a tag is unassigned
    const [pendingKernelRemoval, setPendingKernelRemoval] = useState<KernelEntry | null>(null);

    // Evidence prompt before committing a single-account community tag assignment
    const [pendingTagAssignment, setPendingTagAssignment] = useState<{
        accountTitle: string;
        tagName: string;
        onConfirm: (evidence: string) => Promise<void>;
    } | null>(null);
    const [evidenceText, setEvidenceText] = useState('');

    // Weights
    const [weights, setWeights] = useState<TieWeights>({...DEFAULT_TIE_WEIGHTS});
    // Weights as of the last Run Analysis. The live `weights` drive the inputs and
    // are only committed here on Run Analysis, so the kernel expanded-view scores
    // refresh on the same trigger as the candidates list — not on every keystroke.
    const [appliedWeights, setAppliedWeights] = useState<TieWeights>({...DEFAULT_TIE_WEIGHTS});
    // The weights inputs live in a collapsed "Advanced" disclosure inside the run
    // card. Open-state is UI-only — never exported.
    const [weightsOpen, setWeightsOpen] = useState(false);

    // Candidates
    const [candidates, setCandidates] = useState<CandidateAccount[]>([]);
    const [candidateAllTags, setCandidateAllTags] = useState<Record<number, ITagWithType[]>>({});
    const [isComputing, setIsComputing] = useState(false);
    const [hasRun, setHasRun] = useState(false);
    // Seed ids as of the last run — drives the "results are stale" bar when the
    // seed set changes after a run. Dismissals deliberately don't count as stale
    // (the bar would otherwise be permanent during triage).
    const [lastRunKernelIds, setLastRunKernelIds] = useState<Set<number> | null>(null);
    // Scroll target for the first-run reveal of the candidates card.
    const candidatesCardRef = useRef<HTMLDivElement>(null);
    const prevHasRun = useRef(false);

    // Lazy-loaded, cached tag distribution shown in each candidate's score tooltip.
    // Cleared whenever a new analysis is run (see runAnalysis).
    const [candidateTagDistributions, setCandidateTagDistributions] = useState<Record<number, ITagStat[]>>({});
    const [loadingTagDistributions, setLoadingTagDistributions] = useState<Record<number, boolean>>({});

    const loadCandidateTagDistribution = (candidateId: number) => {
        if (candidateTagDistributions[candidateId] || loadingTagDistributions[candidateId]) return;
        setLoadingTagDistributions(prev => ({...prev, [candidateId]: true}));
        fetchRelatedTagStats(candidateId).then(stats => {
            setCandidateTagDistributions(prev => ({...prev, [candidateId]: stats}));
            setLoadingTagDistributions(prev => ({...prev, [candidateId]: false}));
        });
    };

    // Excluded accounts
    const [excludedAccounts, setExcludedAccounts] = useState<CandidateAccount[]>([]);
    const [excludedOpen, setExcludedOpen] = useState(false);

    // Export / import
    const [importError, setImportError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Page-level feedback snackbar (copy results, analysis errors, dismiss/add
    // confirmations). `undoId` renders an Undo action restoring that dismissed
    // candidate.
    const [feedback, setFeedback] = useState<{
        severity: 'success' | 'error' | 'info';
        message: string;
        undoId?: number;
    } | null>(null);

    // URL state: the selected community tag id is reflected in the `communityTag`
    // search param (absent when no tag is selected).
    const [searchParams, setSearchParams] = useSearchParams();
    const initializedFromUrl = useRef(false);

    // Initialize the community tag from the URL on first load. With no param the
    // tag stays null; with a valid id we resolve the full tag from the tag-kernel
    // dropdown (which always contains the tag itself) and seed the kernel from it.
    React.useEffect(() => {
        const raw = searchParams.get(COMMUNITY_TAG_PARAM);
        const tagId = raw !== null ? parseInt(raw, 10) : NaN;
        if (Number.isNaN(tagId)) {
            initializedFromUrl.current = true;
            return;
        }
        let cancelled = false;
        (async () => {
            setTagTransitionLoading(true);
            try {
                const resp: TagKernelResponse = await fetchTagKernelAccounts(tagId);
                if (cancelled) return;
                const tag = resp.dropdown.tags.find(t => t.id === tagId) ?? null;
                if (tag) {
                    setCommunityTag(tag);
                    setCommunityDropdown(resp.dropdown);
                    setKernelEntries(resp.accounts.map(a => ({
                        account: tagKernelAccountToSearchResult(a),
                        manuallyAdded: false,
                        tagSources: a.applied_tags,
                    })));
                    setExcludedAccounts(resp.dismissals.map(dismissedToCandidate));
                }
            } finally {
                if (!cancelled) {
                    setTagTransitionLoading(false);
                    initializedFromUrl.current = true;
                }
            }
        })();
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Keep the URL search param and document title in sync with the selected tag.
    // Guarded so it does not clobber the param before initialization has read it.
    React.useEffect(() => {
        document.title = communityTag ? `${communityTag.name} | ${BASE_TITLE}` : BASE_TITLE;
        if (!initializedFromUrl.current) return;
        setSearchParams(prev => {
            const next = new URLSearchParams(prev);
            if (communityTag?.id != null) {
                next.set(COMMUNITY_TAG_PARAM, String(communityTag.id));
            } else {
                next.delete(COMMUNITY_TAG_PARAM);
            }
            return next;
        }, {replace: true});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [communityTag]);

    // ── Derived ───────────────────────────────────────────────────────────────

    const kernelIds = useMemo(() => kernelEntries.map(e => e.account.id), [kernelEntries]);
    const kernelIdSet = useMemo(() => new Set(kernelIds), [kernelIds]);
    const excludedIds = useMemo(() => excludedAccounts.map(a => a.id), [excludedAccounts]);
    const excludedIdSet = useMemo(() => new Set(excludedIds), [excludedIds]);
    const visibleCandidates = useMemo(() => candidates.filter(c => !excludedIdSet.has(c.id)), [candidates, excludedIdSet]);
    const hasVerifiedVisible = useMemo(() => visibleCandidates.some(c => c.is_verified === true), [visibleCandidates]);

    const candidateFiltersActive = isDisplayFilterActive(candidateFilters);

    const shownCandidates = useMemo(
        () => visibleCandidates.filter(c => !isHiddenByFilters(c, candidateFilters)),
        [visibleCandidates, candidateFilters],
    );

    // ── Staleness ─────────────────────────────────────────────────────────────

    // The candidates list is stale when the seed set or the weights changed
    // since the run that produced it. Dismissals don't count (see state note).
    const weightsStale = useMemo(
        () => (Object.keys(weights) as (keyof TieWeights)[]).some(k => weights[k] !== appliedWeights[k]),
        [weights, appliedWeights],
    );
    const kernelChangedSinceRun = useMemo(() => {
        if (!lastRunKernelIds) return false;
        if (lastRunKernelIds.size !== kernelIds.length) return true;
        return kernelIds.some(id => !lastRunKernelIds.has(id));
    }, [lastRunKernelIds, kernelIds]);
    const resultsStale = hasRun && kernelIds.length > 0 && (kernelChangedSinceRun || weightsStale);

    const weightsModified = useMemo(
        () => (Object.keys(DEFAULT_TIE_WEIGHTS) as (keyof TieWeights)[]).some(k => weights[k] !== DEFAULT_TIE_WEIGHTS[k]),
        [weights],
    );

    // Archiver labels available for the "Followed by…" filter. Every enriched
    // account carries the full archiver roster, so the union across the
    // candidates and loaded kernel details is that roster (sorted).
    const archiverLabels = useMemo(() => {
        const labels = new Set<string>();
        for (const c of visibleCandidates) for (const e of c.archiver_access ?? []) labels.add(e.label);
        for (const d of Object.values(kernelDetails)) for (const e of d.archiver_access ?? []) labels.add(e.label);
        return Array.from(labels).sort((a, b) => a.localeCompare(b));
    }, [visibleCandidates, kernelDetails]);

    const communityTagIds = useMemo(
        () => communityDropdown ? new Set(communityDropdown.tags.map(t => t.id!)) : new Set<number>(),
        [communityDropdown],
    );

    const candidateCommunityTags = useMemo(() => {
        if (!communityTagIds.size) return {} as Record<number, ITagWithType[]>;
        return Object.fromEntries(
            Object.entries(candidateAllTags).map(([id, tags]) =>
                [id, tags.filter(t => communityTagIds.has(t.id!))]
            )
        ) as Record<number, ITagWithType[]>;
    }, [candidateAllTags, communityTagIds]);

    const candidateCommunityTagIdSets = useMemo(() =>
            Object.fromEntries(
                Object.entries(candidateCommunityTags).map(([id, tags]) =>
                    [id, new Set(tags.map(t => t.id!))]
                )
            ) as Record<number, Set<number>>,
        [candidateCommunityTags],
    );

    // ── Kernel expanded-view detail ───────────────────────────────────────────

    // Fetch per-account detail (score against the rest of the kernel, thumbnails)
    // when the expanded view is active. Re-runs whenever kernel membership changes
    // (every member's score depends on the full kernel composition) or the applied
    // weights change (committed on Run Analysis, so this does not refetch on every
    // weight keystroke). This detail is never exported.
    useEffect(() => {
        if (!kernelExpandedView || kernelIds.length === 0) return;
        let cancelled = false;
        setKernelDetailsLoading(true);
        fetchKernelDetails(kernelIds, appliedWeights)
            .then(resp => {
                if (cancelled) return;
                const map: Record<number, CandidateAccount> = {};
                for (const c of resp.candidates) map[c.id] = c;
                setKernelDetails(map);
            })
            .catch(() => {
                if (cancelled) return;
                setFeedback({
                    severity: 'error',
                    message: "Couldn't load seed account details — check your connection and try again.",
                });
            })
            .finally(() => {
                if (!cancelled) setKernelDetailsLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [kernelExpandedView, kernelIds, appliedWeights]);

    // Kernel entries after display filters. Filtering only applies in expanded
    // view (compact pills and their copy stay unfiltered). An entry whose detail
    // hasn't loaded yet is treated as not-hidden so it shows while loading.
    const filteredKernelEntries = useMemo(
        () => kernelExpandedView
            ? kernelEntries.filter(e => {
                const d = kernelDetails[e.account.id];
                return !d || !isHiddenByFilters(d, kernelFilters);
            })
            : kernelEntries,
        [kernelExpandedView, kernelEntries, kernelDetails, kernelFilters],
    );

    const kernelPageCount = Math.max(1, Math.ceil(filteredKernelEntries.length / KERNEL_PAGE_SIZE));
    const clampedKernelPage = Math.min(kernelPage, kernelPageCount);
    const pagedKernelEntries = useMemo(
        () => filteredKernelEntries.slice((clampedKernelPage - 1) * KERNEL_PAGE_SIZE, clampedKernelPage * KERNEL_PAGE_SIZE),
        [filteredKernelEntries, clampedKernelPage],
    );

    // ── Community tag selection ───────────────────────────────────────────────

    // Discard the current suggestions list (and everything derived from the last
    // run). Called whenever the tag binding changes, since a suggestions list
    // computed for the previous binding would be stale and confusing.
    const resetSuggestions = () => {
        setCandidates([]);
        setCandidateAllTags({});
        setCandidateTagDistributions({});
        setLoadingTagDistributions({});
        setHasRun(false);
        setLastRunKernelIds(null);
    };

    // Reveal the candidates card on the first run only (never on refreshes —
    // the user is already looking at the list by then).
    useEffect(() => {
        if (hasRun && !prevHasRun.current && candidatesCardRef.current) {
            const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            candidatesCardRef.current.scrollIntoView({
                behavior: reduceMotion ? 'auto' : 'smooth',
                block: 'start',
            });
        }
        prevHasRun.current = hasRun;
    }, [hasRun]);

    const handleCommunityTagChange = async (tag: ITagWithType | null) => {
        if (!tag) {
            // Clear tag mode: keep kernel entries but clear tagSources indicators
            setCommunityTag(null);
            setCommunityDropdown(null);
            resetSuggestions();
            return;
        }

        setTagTransitionLoading(true);
        try {
            const resp: TagKernelResponse = await fetchTagKernelAccounts(tag.id!);
            // The transition popup (with its "attach tag to existing kernel"
            // option) is only useful when going from ad-hoc mode to tag-bound
            // mode — the user built an ad-hoc kernel and now wants to bind it to
            // a tag. When already tag-bound (switching tag A → tag B), the
            // existing kernel belongs to tag A and the user won't want to carry
            // it over to tag B, so we skip the popup and load tag B fresh,
            // exactly as if it had been selected from a clean state.
            if (kernelEntries.length === 0 || communityTag) {
                // No existing kernel, or already tag-bound — set directly.
                setCommunityTag(tag);
                setCommunityDropdown(resp.dropdown);
                const newEntries: KernelEntry[] = resp.accounts.map(a => ({
                    account: tagKernelAccountToSearchResult(a),
                    manuallyAdded: false,
                    tagSources: a.applied_tags,
                }));
                setKernelEntries(newEntries);
                setExcludedAccounts(resp.dismissals.map(dismissedToCandidate));
                resetSuggestions();
            } else {
                // Ad-hoc kernel populated — ask for confirmation
                setTagTransitionPending({
                    tag,
                    tagKernelAccounts: resp.accounts,
                    dropdown: resp.dropdown,
                    dismissals: resp.dismissals,
                });
                setTagTransitionApplyToExisting(false);
            }
        } finally {
            setTagTransitionLoading(false);
        }
    };

    const confirmTagTransition = async () => {
        if (!tagTransitionPending) return;
        const {tag, tagKernelAccounts, dropdown, dismissals} = tagTransitionPending;

        // Optionally attach the tag to all accounts currently in the kernel
        if (tagTransitionApplyToExisting && kernelIds.length > 0) {
            await batchAnnotate('account', kernelIds, [{id: tag.id!}]);
            // Update tagSources for existing kernel entries
            setKernelEntries(prev => prev.map(e => ({
                ...e,
                tagSources: e.tagSources.some(t => t.id === tag.id)
                    ? e.tagSources
                    : [...e.tagSources, tag],
            })));
        }

        // Add tag-based accounts not already in kernel
        const newEntries: KernelEntry[] = tagKernelAccounts
            .filter(a => !kernelIdSet.has(a.id))
            .map(a => ({
                account: tagKernelAccountToSearchResult(a),
                manuallyAdded: false,
                tagSources: a.applied_tags,
            }));
        setKernelEntries(prev => [...prev, ...newEntries]);

        // Now bound to this tag — its saved dismissals replace any prior list.
        setExcludedAccounts(dismissals.map(dismissedToCandidate));

        setCommunityTag(tag);
        setCommunityDropdown(dropdown);
        setTagTransitionPending(null);
    };

    // ── Kernel management ─────────────────────────────────────────────────────

    const addToKernel = (result: SearchResult) => {
        if (kernelIdSet.has(result.id)) return;
        const urlSuffix = result.metadata?.url_suffix as string | null | undefined;
        const displayName = result.metadata?.display_name as string | null | undefined;
        const title = displayName
            ? `${urlSuffix} (${displayName})`
            : (urlSuffix ?? result.title);
        setKernelEntries(prev => [...prev, {
            account: {...result, title},
            manuallyAdded: true,
            tagSources: [],
        }]);
    };

    const removeFromKernel = (id: number) => {
        setKernelEntries(prev => prev.filter(e => e.account.id !== id));
    };

    // Remove the community tag(s) justifying this entry's inclusion from the
    // account in the database, then take it out of the kernel. Backs both the
    // pill modal's confirm action and the expanded view's strip button.
    const stripTagsAndRemove = async (entry: KernelEntry) => {
        for (const tag of entry.tagSources) {
            await removeAccountTag(entry.account.id, tag.id!);
        }
        removeFromKernel(entry.account.id);
    };

    // Take an account out of the kernel (compact pill X). In tag mode, an
    // account tagged with the community tag (or a subtag) would be re-seeded on
    // the next tag load, so a dialog asks whether to also strip the tag(s).
    const takeOutOfKernel = (entry: KernelEntry) => {
        if (communityDropdown && entry.tagSources.length > 0) {
            setPendingKernelTagRemoval(entry);
        } else {
            removeFromKernel(entry.account.id);
        }
    };

    const confirmKernelTagRemoval = async () => {
        const entry = pendingKernelTagRemoval;
        if (!entry) return;
        await stripTagsAndRemove(entry);
        setPendingKernelTagRemoval(null);
    };

    // Toggle a community tag on a kernel entry
    const handleKernelTagToggle = async (entry: KernelEntry, tag: ITagWithType) => {
        const isAssigned = entry.tagSources.some(t => t.id === tag.id);
        if (isAssigned) {
            // Remove tag from account
            await removeAccountTag(entry.account.id, tag.id!);
            const newSources = entry.tagSources.filter(t => t.id !== tag.id);
            setKernelEntries(prev => prev.map(e =>
                e.account.id === entry.account.id ? {...e, tagSources: newSources} : e
            ));
            if (newSources.length === 0 && !entry.manuallyAdded) {
                setPendingKernelRemoval(entry);
            }
        } else {
            setPendingTagAssignment({
                accountTitle: entry.account.title,
                tagName: tag.name,
                onConfirm: async (evidence) => {
                    const notes = evidence.trim() ? `Evidence in support of assignment: ${evidence.trim()}` : null;
                    await batchAnnotate('account', [entry.account.id], [{id: tag.id!, notes}]);
                    setKernelEntries(prev => prev.map(e => {
                        if (e.account.id !== entry.account.id) return e;
                        return {...e, tagSources: [...e.tagSources, tag]};
                    }));
                },
            });
            setEvidenceText('');
        }
    };

    // ── Candidates ────────────────────────────────────────────────────────────

    const runAnalysis = async () => {
        setIsComputing(true);
        // Invalidate cached tag distributions — scores (and thus the relevant
        // candidates) may have changed for this new run.
        setCandidateTagDistributions({});
        setLoadingTagDistributions({});
        try {
            const resp: CommunityCandidatesResponse = await fetchCommunityCandidates(
                kernelIds, excludedIds, weights
            );
            setCandidates(resp.candidates);
            // Commit the weights and seed set used for this run so the kernel
            // expanded-view scores refresh against the same weights as the
            // candidates, and so staleness is measured against this snapshot.
            setAppliedWeights(weights);
            setLastRunKernelIds(new Set(kernelIds));
            setHasRun(true);

            // In tag mode, bulk-fetch community tags for all returned candidates
            if (communityTag && resp.candidates.length > 0) {
                try {
                    const allTags = await fetchTagsForSearchResults('accounts', resp.candidates.map(c => c.id));
                    setCandidateAllTags(allTags);
                } catch {
                    setCandidateAllTags({});
                    setFeedback({
                        severity: 'error',
                        message: "Candidates loaded, but their community-tag info couldn't be fetched.",
                    });
                }
            } else {
                setCandidateAllTags({});
            }
        } catch {
            setFeedback({
                severity: 'error',
                message: 'Analysis failed — check your connection and try again.',
            });
        } finally {
            setIsComputing(false);
        }
    };

    const addCandidateToKernel = (candidate: CandidateAccount) => {
        if (kernelIdSet.has(candidate.id)) return;
        const tagSources: ITagWithType[] = [];
        setKernelEntries(prev => [...prev, {
            account: {
                id: candidate.id,
                page: 'account',
                title: candidateTitle(candidate),
                details: candidate.bio ?? undefined,
                thumbnails: candidate.thumbnails,
                metadata: {media_count: candidate.media_count, url_suffix: candidate.url_suffix, display_name: candidate.display_name},
            },
            manuallyAdded: true,
            tagSources,
        }]);
        setCandidates(prev => prev.filter(c => c.id !== candidate.id));
        // The card vanishes from the list — say where it went.
        setFeedback({severity: 'success', message: `Added ${candidateTitle(candidate)} to the seed accounts`});
    };

    // Toggle a community tag on a candidate account
    const handleCandidateTagToggle = async (candidate: CandidateAccount, tag: ITagWithType) => {
        const currentTags = candidateAllTags[candidate.id] ?? [];
        const isAssigned = currentTags.some(t => t.id === tag.id);

        if (isAssigned) {
            await removeAccountTag(candidate.id, tag.id!);
            setCandidateAllTags(prev => ({
                ...prev,
                [candidate.id]: (prev[candidate.id] ?? []).filter(t => t.id !== tag.id),
            }));
        } else {
            const newTagEntry = communityDropdown?.tags.find(t => t.id === tag.id) ?? tag;
            setPendingTagAssignment({
                accountTitle: candidateTitle(candidate),
                tagName: tag.name,
                onConfirm: async (evidence) => {
                    const notes = evidence.trim() ? `Evidence in support of assignment: ${evidence.trim()}` : null;
                    await batchAnnotate('account', [candidate.id], [{id: tag.id!, notes}]);
                    setCandidateAllTags(prev => ({
                        ...prev,
                        [candidate.id]: [...(prev[candidate.id] ?? []), newTagEntry],
                    }));
                    const tagSources = [newTagEntry, ...(candidateCommunityTags[candidate.id] ?? []).filter(t => t.id !== tag.id)];
                    if (!kernelIdSet.has(candidate.id)) {
                        setKernelEntries(prev => [...prev, {
                            account: {
                                id: candidate.id,
                                page: 'account',
                                title: candidateTitle(candidate),
                                details: candidate.bio ?? undefined,
                                thumbnails: candidate.thumbnails,
                                metadata: {media_count: candidate.media_count, url_suffix: candidate.url_suffix, display_name: candidate.display_name},
                            },
                            manuallyAdded: false,
                            tagSources,
                        }]);
                        setCandidates(prev => prev.filter(c => c.id !== candidate.id));
                        // The card vanishes from the list — say where it went.
                        setFeedback({
                            severity: 'success',
                            message: `Tagged ${candidateTitle(candidate)} and added it to the seed accounts`,
                        });
                    }
                },
            });
            setEvidenceText('');
        }
    };

    // In tag-bound mode, dismissals are persisted to the tag so they survive a
    // reload of the page for the same tag. The tag's own list only — the tag
    // hierarchy is intentionally not consulted. Fire-and-forget; a failed save
    // just means the dismissal isn't remembered across reloads.
    const persistDismissals = (next: CandidateAccount[]) => {
        const tagId = communityTag?.id;
        if (tagId == null) return;
        saveTagDismissals(tagId, next.map(candidateToDismissed)).catch(() => {
        });
    };

    const excludeCandidate = (candidate: CandidateAccount) => {
        const next = [...excludedAccounts, candidate];
        setExcludedAccounts(next);
        persistDismissals(next);
        // Dismissal is a single unconfirmed click (and persists in tag mode) —
        // offer an immediate undo.
        setFeedback({
            severity: 'info',
            message: `Dismissed ${candidateTitle(candidate)}`,
            undoId: candidate.id,
        });
    };

    const restoreCandidate = (id: number) => {
        const next = excludedAccounts.filter(a => a.id !== id);
        setExcludedAccounts(next);
        persistDismissals(next);
    };

    const autoRemoveVerified = () => {
        const verified = visibleCandidates.filter(c => c.is_verified === true);
        const next = [...excludedAccounts, ...verified];
        setExcludedAccounts(next);
        persistDismissals(next);
        setFeedback({
            severity: 'info',
            message: `Dismissed ${verified.length} verified account${verified.length === 1 ? '' : 's'}`,
        });
    };

    // ── Export / import ───────────────────────────────────────────────────────

    const copyKernelAsCsv = async () => {
        const escapeCell = (v: string) =>
            /[",\r\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
        // In expanded view the copy reflects the active display filters (only
        // un-hidden members are copied); in compact view there is no filtering.
        const entriesToCopy = kernelExpandedView ? filteredKernelEntries : kernelEntries;
        const hidden = kernelEntries.length - entriesToCopy.length;
        const rows: string[] = ['url,tags'];
        let skipped = 0;
        for (const entry of entriesToCopy) {
            const suffix = entry.account.metadata?.url_suffix as string | null | undefined;
            if (!suffix) {
                skipped++;
                continue;
            }
            const url = `https://www.instagram.com/${suffix}/`;
            const tags = entry.tagSources.map(t => t.name).join(';');
            rows.push(`${escapeCell(url)},${escapeCell(tags)}`);
        }
        const csv = rows.join('\n');
        try {
            await navigator.clipboard.writeText(csv);
            const copied = rows.length - 1;
            const hiddenNote = hidden > 0 ? ` (${hidden} hidden by filters)` : '';
            const skippedNote = skipped > 0 ? ` (${skipped} skipped — no url_suffix)` : '';
            setFeedback({
                severity: 'success',
                message: `Copied ${copied} row${copied === 1 ? '' : 's'} to clipboard${hiddenNote}${skippedNote}`,
            });
        } catch (err) {
            setFeedback({
                severity: 'error',
                message: `Failed to copy: ${err instanceof Error ? err.message : String(err)}`,
            });
        }
    };

    // Copy the candidate URLs (after display filters) as a newline-delimited
    // list. Unlike the kernel copy there is no tags column — by definition a
    // suggestion is not tagged with the community tag (or a subtag) — so a
    // single-column, header-less list of URLs is enough.
    const copyCandidatesAsUrls = async () => {
        const urls: string[] = [];
        let skipped = 0;
        for (const candidate of shownCandidates) {
            if (!candidate.url_suffix) {
                skipped++;
                continue;
            }
            urls.push(`https://www.instagram.com/${candidate.url_suffix}/`);
        }
        try {
            await navigator.clipboard.writeText(urls.join('\n'));
            const skippedNote = skipped > 0 ? ` (${skipped} skipped — no url_suffix)` : '';
            setFeedback({
                severity: 'success',
                message: `Copied ${urls.length} URL${urls.length === 1 ? '' : 's'} to clipboard${skippedNote}`,
            });
        } catch (err) {
            setFeedback({
                severity: 'error',
                message: `Failed to copy: ${err instanceof Error ? err.message : String(err)}`,
            });
        }
    };

    const exportState = () => {
        const state: CommunityStateExport = {
            version: 1,
            community_tag: communityTag,
            community_dropdown: communityDropdown,
            kernel: kernelEntries.map(({account, manuallyAdded, tagSources}) => ({
                account: sanitizeForExport(account),
                manuallyAdded,
                tagSources,
            })),
            weights,
            excluded: excludedAccounts.map(sanitizeForExport),
        };
        const datePart = new Date().toISOString().slice(0, 10);
        // Sanitize the tag name into a filesystem-safe slug (drop punctuation
        // like . and , that would produce an illegal/misleading filename).
        const tagSlug = communityTag
            ? communityTag.name
                .replace(/[^a-zA-Z0-9-_ ]/g, '')
                .trim()
                .replace(/\s+/g, '-')
            : '';
        const fileName = tagSlug
            ? `community-${tagSlug}-${datePart}.json`
            : `community-${datePart}.json`;
        downloadTextFile(
            JSON.stringify(state, null, 2),
            fileName,
            'application/json',
        );
    };

    const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        e.target.value = '';
        const reader = new FileReader();
        reader.onload = (ev) => {
            try {
                const parsed = JSON.parse(ev.target?.result as string);
                if (!isCommunityStateExport(parsed)) {
                    setImportError('Invalid state file — missing required fields or wrong version.');
                    return;
                }
                setCommunityTag(parsed.community_tag);
                setCommunityDropdown(parsed.community_dropdown);
                setKernelEntries(parsed.kernel.map(e => ({
                    account: sanitizeForExport(e.account),
                    manuallyAdded: e.manuallyAdded,
                    tagSources: e.tagSources,
                })));
                setWeights({...DEFAULT_TIE_WEIGHTS, ...parsed.weights});
                setExcludedAccounts(parsed.excluded.map(sanitizeForExport));
                setCandidates([]);
                setCandidateAllTags({});
                setHasRun(false);
                setLastRunKernelIds(null);
            } catch {
                setImportError('Could not parse file — make sure it is a valid JSON export.');
            }
        };
        reader.readAsText(file);
    };

    // ── Community tag selector label ──────────────────────────────────────────

    const communityTagLabel = communityTag
        ? `Community Tag: ${communityTag.name}`
        : kernelEntries.length === 0
            ? 'Base community on a tag (optional)'
            : 'Attach a tag to this community';

    // ── Render ────────────────────────────────────────────────────────────────

    return (
        <div className="page-wrap">
            <TopNavBar>Community Detection</TopNavBar>
            <div className="page-content content-wrap">

                {/* ── Hidden file input for import ─────────────────────────── */}
                <input
                    type="file"
                    accept=".json"
                    style={{display: 'none'}}
                    ref={fileInputRef}
                    onChange={handleImportFile}
                />

                {/* ── Orientation + export / import bar ─────────────────────── */}
                <Stack direction="row" justifyContent="space-between" alignItems="center" gap={2} sx={{mb: 1.5}}>
                    <Typography variant="body2" color="text.secondary">
                        Start from a few accounts you know belong to a community — the tool finds
                        other accounts that interact with them.
                    </Typography>
                    <Stack direction="row" gap={1} sx={{flexShrink: 0}}>
                        <Tooltip title="Load a previously exported state file">
                            <Button
                                size="small"
                                variant="outlined"
                                startIcon={<FileUploadOutlinedIcon/>}
                                onClick={() => fileInputRef.current?.click()}
                            >
                                Import state
                            </Button>
                        </Tooltip>
                        <Tooltip title="Save current seed accounts, weights and dismissals to a JSON file">
                            <Button
                                size="small"
                                variant="outlined"
                                startIcon={<FileDownloadOutlinedIcon/>}
                                onClick={exportState}
                            >
                                Export state
                            </Button>
                        </Tooltip>
                    </Stack>
                </Stack>

                {/* ── Import error snackbar ─────────────────────────────────── */}
                <Snackbar
                    open={importError !== null}
                    autoHideDuration={5000}
                    onClose={() => setImportError(null)}
                    anchorOrigin={{vertical: 'bottom', horizontal: 'center'}}
                >
                    <Alert severity="error" onClose={() => setImportError(null)} variant="filled">
                        {importError}
                    </Alert>
                </Snackbar>

                {/* ── Feedback snackbar (copy / errors / dismiss-undo) ─────── */}
                <Snackbar
                    open={feedback !== null}
                    autoHideDuration={feedback?.undoId != null ? 6000 : 3000}
                    onClose={(_, reason) => {
                        if (reason === 'clickaway') return;
                        setFeedback(null);
                    }}
                    anchorOrigin={{vertical: 'bottom', horizontal: 'center'}}
                >
                    <Alert
                        severity={feedback?.severity ?? 'success'}
                        onClose={() => setFeedback(null)}
                        variant="filled"
                        action={feedback?.undoId != null ? (
                            <Stack direction="row" alignItems="center" gap={0.5}>
                                <Button
                                    color="inherit" size="small"
                                    onClick={() => {
                                        restoreCandidate(feedback.undoId!);
                                        setFeedback(null);
                                    }}
                                >
                                    Undo
                                </Button>
                                <IconButton size="small" color="inherit" onClick={() => setFeedback(null)}>
                                    <CloseIcon fontSize="small"/>
                                </IconButton>
                            </Stack>
                        ) : undefined}
                    >
                        {feedback?.message}
                    </Alert>
                </Snackbar>

                {/* ── Kernel modal ─────────────────────────────────────────── */}
                <Dialog open={kernelModalOpen} onClose={() => setKernelModalOpen(false)}
                        maxWidth="sm" fullWidth>
                    <DialogTitle sx={{pr: 6}}>
                        Add seed accounts
                        <IconButton onClick={() => setKernelModalOpen(false)} size="small"
                                    sx={{position: 'absolute', right: 8, top: 8}}>
                            <CloseIcon/>
                        </IconButton>
                    </DialogTitle>
                    <DialogContent dividers sx={{p: 2}}>
                        <SearchPanel
                            query={KERNEL_SEARCH_QUERY}
                            onSearch={() => {
                            }}
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
                            {kernelEntries.length} seed account{kernelEntries.length !== 1 ? 's' : ''}
                        </Typography>
                        <Button variant="contained" onClick={() => setKernelModalOpen(false)}>Done</Button>
                    </DialogActions>
                </Dialog>

                {/* ── Evidence prompt for single-account tag assignment ─────── */}
                <Dialog
                    open={pendingTagAssignment !== null}
                    onClose={() => setPendingTagAssignment(null)}
                    maxWidth="sm"
                    fullWidth
                >
                    <DialogTitle>Assign Tag</DialogTitle>
                    <DialogContent dividers>
                        <Stack gap={1.5}>
                            <Typography variant="body2">
                                Assigning <strong>{pendingTagAssignment?.tagName}</strong> to{' '}
                                <strong>{pendingTagAssignment?.accountTitle}</strong>.
                            </Typography>
                            <TextField
                                label="Evidence (explanation / link to evidence)"
                                multiline
                                minRows={2}
                                fullWidth
                                autoFocus
                                value={evidenceText}
                                onChange={e => setEvidenceText(e.target.value)}
                                placeholder="Optional — paste a URL, describe a connection, or leave blank"
                            />
                        </Stack>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setPendingTagAssignment(null)}>Cancel</Button>
                        <Button
                            variant="contained"
                            onClick={async () => {
                                if (!pendingTagAssignment) return;
                                await pendingTagAssignment.onConfirm(evidenceText);
                                setPendingTagAssignment(null);
                                setEvidenceText('');
                            }}
                        >
                            Assign
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* ── Untagged kernel account removal modal ─────────────────── */}
                <Dialog
                    open={pendingKernelRemoval !== null}
                    onClose={() => setPendingKernelRemoval(null)}
                    maxWidth="sm"
                    fullWidth
                >
                    <DialogTitle>Keep account in seeds?</DialogTitle>
                    <DialogContent dividers>
                        <Typography variant="body2">
                            After removing this tag, <strong>{pendingKernelRemoval?.account.title}</strong> will
                            have no community tag justifying its inclusion in the seed accounts. Should it be
                            removed from the seeds, or kept for analysis?
                        </Typography>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setPendingKernelRemoval(null)}>Keep in seeds</Button>
                        <Button
                            variant="contained"
                            color="error"
                            onClick={() => {
                                if (!pendingKernelRemoval) return;
                                removeFromKernel(pendingKernelRemoval.account.id);
                                setPendingKernelRemoval(null);
                            }}
                        >
                            Remove from seeds
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* ── Kernel removal modal (compact pill X, tag mode) ───────── */}
                <Dialog
                    open={pendingKernelTagRemoval !== null}
                    onClose={() => setPendingKernelTagRemoval(null)}
                    maxWidth="sm"
                    fullWidth
                >
                    <DialogTitle>Also remove the community tag(s)?</DialogTitle>
                    <DialogContent dividers>
                        <Typography variant="body2">
                            <strong>{pendingKernelTagRemoval?.account.title}</strong> is in the seed accounts
                            because of the following community tag(s):
                        </Typography>
                        <Box component="ul" sx={{pl: 2.5, mt: 1, mb: 1}}>
                            {pendingKernelTagRemoval?.tagSources.map(t => (
                                <li key={t.id}>
                                    <Typography variant="body2">{t.name}</Typography>
                                </li>
                            ))}
                        </Box>
                        <Typography variant="body2">
                            If you remove it from the seeds <strong>without</strong> removing the tag(s),
                            it will automatically return to the seeds the next time the community page is
                            loaded for this tag.
                        </Typography>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setPendingKernelTagRemoval(null)}>Cancel</Button>
                        <Button
                            onClick={() => {
                                if (!pendingKernelTagRemoval) return;
                                removeFromKernel(pendingKernelTagRemoval.account.id);
                                setPendingKernelTagRemoval(null);
                            }}
                        >
                            Remove from seeds only
                        </Button>
                        <Button variant="contained" color="error" onClick={confirmKernelTagRemoval}>
                            Remove tag(s) &amp; remove from seeds
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* ── Tag transition confirmation modal ─────────────────────── */}
                <Dialog
                    open={tagTransitionPending !== null}
                    onClose={() => setTagTransitionPending(null)}
                    maxWidth="sm"
                    fullWidth
                >
                    <DialogTitle>Switch to Tag Mode?</DialogTitle>
                    <DialogContent dividers>
                        <Stack gap={1.5}>
                            <Typography variant="body2">
                                You selected <strong>{tagTransitionPending?.tag.name}</strong> as the community tag.
                                The following changes will take effect:
                            </Typography>
                            <Box component="ul" sx={{pl: 2.5, m: 0}}>
                                <li>
                                    <Typography variant="body2">
                                        <strong>{tagTransitionPending?.tagKernelAccounts.filter(a => !kernelIdSet.has(a.id)).length ?? 0}</strong> account(s)
                                        tagged with <em>{tagTransitionPending?.tag.name}</em> (or its subtags) will be
                                        added to the seed accounts.
                                    </Typography>
                                </li>
                            </Box>
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={tagTransitionApplyToExisting}
                                        onChange={e => setTagTransitionApplyToExisting(e.target.checked)}
                                        size="small"
                                    />
                                }
                                label={
                                    <Typography variant="body2">
                                        Also attach the <strong>{tagTransitionPending?.tag.name}</strong> tag
                                        to the {kernelEntries.length} account(s) already in the seeds
                                    </Typography>
                                }
                            />
                        </Stack>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setTagTransitionPending(null)}>Cancel</Button>
                        <Button variant="contained" onClick={confirmTagTransition}>Confirm</Button>
                    </DialogActions>
                </Dialog>

                <Stack gap={0}>

                    {/* ── Community tag selector ───────────────────────────── */}
                    <Paper variant="outlined" sx={{p: 2.5, borderRadius: 2}}>
                        <Stack direction="row" alignItems="center" gap={1.5}>
                            <Box sx={{flex: 1}}>
                                <TagSelector
                                    selectedTags={communityTag ? [communityTag] : []}
                                    label={communityTagLabel}
                                    onChange={(tags) => handleCommunityTagChange(tags[0] ?? null)}
                                    readOnly={tagTransitionLoading}
                                    single
                                    entity="account"
                                />
                            </Box>
                            {tagTransitionLoading && <CircularProgress size={20}/>}
                            {communityTag && (
                                <Tooltip
                                    title="Detach from the tag — keeps the current seed accounts; tag assignments stay in the database">
                                    <IconButton
                                        size="small"
                                        onClick={() => handleCommunityTagChange(null)}
                                        sx={{flexShrink: 0}}
                                    >
                                        <CloseIcon fontSize="small"/>
                                    </IconButton>
                                </Tooltip>
                            )}
                        </Stack>
                        {communityTag && (
                            <Typography variant="caption" color="text.secondary" sx={{mt: 0.75, display: 'block'}}>
                                Tag mode active — seed accounts loaded from accounts tagged
                                with <strong>{communityTag.name}</strong> (and its subtags).
                                Tag assignments are saved to the database.
                            </Typography>
                        )}
                    </Paper>

                    <Box sx={{width: 2, height: 16, bgcolor: 'divider', mx: 'auto'}}/>

                    {/* ── Step 1: Kernel ───────────────────────────────────── */}
                    <Paper variant="outlined" sx={{p: 2.5, borderRadius: 2}}>
                        <SectionHeader
                            step={1}
                            title="Seed accounts"
                            active={kernelEntries.length > 0}
                            action={
                                <Stack direction="row" spacing={1} alignItems="center">
                                    {kernelEntries.length > 0 && kernelExpandedView && (
                                        <AccountDisplayFilters value={kernelFilters} onChange={setKernelFilters}
                                                              showArchiverSection={canViewArchiver}
                                                              archiverLabels={archiverLabels}/>
                                    )}
                                    {kernelEntries.length > 0 && (
                                        <ToggleButtonGroup
                                            size="small"
                                            exclusive
                                            value={kernelExpandedView ? 'expanded' : 'compact'}
                                            onChange={(_, v) => {
                                                if (v !== null) setKernelExpandedView(v === 'expanded');
                                            }}
                                            sx={{flexShrink: 0}}
                                        >
                                            <ToggleButton value="compact">
                                                <Tooltip title="Compact view">
                                                    <ViewListIcon fontSize="small"/>
                                                </Tooltip>
                                            </ToggleButton>
                                            <ToggleButton value="expanded">
                                                <Tooltip title="Expanded view — show media & scores">
                                                    <ViewAgendaIcon fontSize="small"/>
                                                </Tooltip>
                                            </ToggleButton>
                                        </ToggleButtonGroup>
                                    )}
                                    <Tooltip title="Copy seed accounts as CSV (url, tags)">
                                        <span>
                                            <Button
                                                size="small"
                                                variant="outlined"
                                                startIcon={<ContentCopyIcon/>}
                                                onClick={copyKernelAsCsv}
                                                disabled={kernelEntries.length === 0}
                                                sx={{flexShrink: 0}}
                                            >
                                                Copy to clipboard
                                            </Button>
                                        </span>
                                    </Tooltip>
                                    <Tooltip title="Search and add accounts manually">
                                        <Button
                                            size="small"
                                            variant="contained"
                                            startIcon={<AddIcon/>}
                                            onClick={() => setKernelModalOpen(true)}
                                            sx={{flexShrink: 0}}
                                        >
                                            Add accounts
                                        </Button>
                                    </Tooltip>
                                </Stack>
                            }
                        />

                        {kernelEntries.length > 0 ? (
                            kernelExpandedView ? (
                                filteredKernelEntries.length === 0 ? (
                                    <Typography color="text.secondary" variant="body2">
                                        No seed accounts match the current display filters.
                                    </Typography>
                                ) : (
                                <>
                                    <Stack spacing={0} divider={<Divider/>}>
                                        {pagedKernelEntries.map(entry => (
                                            <KernelAccountCard
                                                key={entry.account.id}
                                                entry={entry}
                                                detail={kernelDetails[entry.account.id]}
                                                loading={kernelDetailsLoading}
                                                communityDropdown={communityDropdown}
                                                onStripAndRemove={() => stripTagsAndRemove(entry)}
                                                onRemoveOnly={() => removeFromKernel(entry.account.id)}
                                                tagDistribution={candidateTagDistributions[entry.account.id]}
                                                tagDistributionLoading={!!loadingTagDistributions[entry.account.id]}
                                                onTagDistributionOpen={() => loadCandidateTagDistribution(entry.account.id)}
                                            />
                                        ))}
                                    </Stack>
                                    {kernelPageCount > 1 && (
                                        <Stack direction="row" justifyContent="center" sx={{mt: 1.5}}>
                                            <Pagination
                                                count={kernelPageCount}
                                                page={clampedKernelPage}
                                                onChange={(_, p) => setKernelPage(p)}
                                                size="small"
                                                color="primary"
                                            />
                                        </Stack>
                                    )}
                                </>
                                )
                            ) : (
                                <Stack direction="row" flexWrap="wrap" gap={1}>
                                    {kernelEntries.map(entry => (
                                        <KernelAccountPill
                                            key={entry.account.id}
                                            entry={entry}
                                            communityDropdown={communityDropdown}
                                            onRemove={() => takeOutOfKernel(entry)}
                                            onTagToggle={(tag) => handleKernelTagToggle(entry, tag)}
                                        />
                                    ))}
                                </Stack>
                            )
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
                                    '&:hover': {
                                        borderColor: 'primary.main',
                                        color: 'primary.main',
                                        bgcolor: 'action.hover'
                                    },
                                    transition: 'all 0.15s',
                                }}
                            >
                                <AddIcon sx={{fontSize: '1.1rem', flexShrink: 0}}/>
                                <Typography variant="body2">
                                    Add seed accounts manually, or select a community tag above to seed from a tag
                                </Typography>
                            </Box>
                        )}
                    </Paper>

                    <Box sx={{width: 2, height: 16, bgcolor: 'divider', mx: 'auto'}}/>

                    {/* ── Step 2: Run (weights tucked behind an Advanced disclosure) ── */}
                    <Paper variant="outlined" sx={{p: 2.5, borderRadius: 2}}>
                        <SectionHeader step={2} title="Find connected accounts"/>
                        <Tooltip
                            title={kernelIds.length === 0 ? 'Add at least one seed account first' : ''}
                            disableHoverListener={kernelIds.length > 0}
                        >
                            <span>
                                <Button
                                    variant="contained"
                                    size="large"
                                    disabled={kernelIds.length === 0 || isComputing}
                                    onClick={runAnalysis}
                                    startIcon={
                                        isComputing ?
                                            <CircularProgress size={18} color="inherit"/> :
                                            hasRun ? <AutoModeIcon/> : <AutoAwesomeIcon/>
                                    }
                                    sx={{minWidth: 220}}
                                >
                                    {isComputing ? 'Analyzing…' : (hasRun ? 'Refresh candidates' : 'Find connected accounts')}
                                </Button>
                            </span>
                        </Tooltip>
                        <Stack direction="row" alignItems="center" gap={1} sx={{mt: 1.5}}>
                            <Button
                                variant="text" size="small"
                                onClick={() => setWeightsOpen(p => !p)}
                                endIcon={<ExpandMoreIcon sx={{
                                    transform: weightsOpen ? 'rotate(180deg)' : 'none',
                                    transition: 'transform 0.2s',
                                }}/>}
                                sx={{color: 'text.secondary'}}
                            >
                                Adjust Connection Weights
                            </Button>
                            {weightsModified && (
                                <Tooltip title="Weights differ from the defaults">
                                    <Chip label="modified" size="small" color="warning" variant="outlined"
                                          sx={{height: 20}}/>
                                </Tooltip>
                            )}
                        </Stack>
                        <Collapse in={weightsOpen} unmountOnExit>
                            <Stack direction="column" gap={1} sx={{mt: 1}}>
                                <Typography variant="body2" color="text.secondary">
                                    Adjust how much each interaction type counts towards the strength of
                                    connection between accounts:
                                </Typography>
                                <Stack direction="row" flexWrap="wrap" gap={2} alignItems="center" sx={{mt: 0.5}}>
                                    {(Object.keys(TIE_LABELS) as (keyof TieWeights)[]).map(tie => (
                                        <NumberField
                                            key={tie}
                                            label={TIE_LABELS[tie]}
                                            value={weights[tie]}
                                            min={0}
                                            step={0.1}
                                            size="small"
                                            onValueChange={v => setWeights(prev => ({...prev, [tie]: v ?? 0}))}
                                            sx={{width: 170}}
                                        />
                                    ))}
                                    <Button
                                        variant="text" size="small"
                                        disabled={!weightsModified}
                                        onClick={() => setWeights({...DEFAULT_TIE_WEIGHTS})}
                                    >
                                        Reset to defaults
                                    </Button>
                                </Stack>
                            </Stack>
                        </Collapse>
                    </Paper>

                    {/* ── Candidates ───────────────────────────────────────── */}
                    {hasRun && (
                        <>
                            <Box sx={{display: 'flex', justifyContent: 'center'}}>
                                <Box sx={{width: '2px', height: 16, bgcolor: 'divider'}}/>
                            </Box>
                            <Paper ref={candidatesCardRef} variant="outlined"
                                   sx={{p: 2.5, borderRadius: 2, scrollMarginTop: 80}}>
                                <Stack direction="row" justifyContent="space-between" alignItems="center"
                                       sx={{mb: 0.5}}>
                                    <Typography variant="subtitle1" sx={{fontWeight: 600}}>
                                        Top Candidates
                                        {shownCandidates.length > 0 && (
                                            <Typography component="span" variant="body2" color="text.secondary"
                                                        sx={{ml: 1}}>
                                                {shownCandidates.length} result{shownCandidates.length !== 1 ? 's' : ''}
                                            </Typography>
                                        )}
                                    </Typography>
                                    <Stack direction="row" spacing={1} alignItems="center">
                                        <AccountDisplayFilters value={candidateFilters} onChange={setCandidateFilters}
                                                              showArchiverSection={canViewArchiver}
                                                              archiverLabels={archiverLabels}/>
                                        <Tooltip
                                            title={candidateFiltersActive
                                                ? 'Clear the display filters to dismiss verified accounts — otherwise it would also dismiss verified accounts hidden by the current filters'
                                                : hasVerifiedVisible ? 'Dismiss all verified accounts from the candidates list to screen out celebs and brands' : 'No verified accounts in current results'}>
                                            <span>
                                                <Button variant="outlined" size="small"
                                                        disabled={!hasVerifiedVisible || candidateFiltersActive}
                                                        onClick={autoRemoveVerified} sx={{flexShrink: 0}}>
                                                    Dismiss all verified
                                                </Button>
                                            </span>
                                        </Tooltip>
                                        <Tooltip title="Copy candidate URLs (one per line) to clipboard">
                                            <span>
                                                <Button
                                                    variant="outlined" size="small"
                                                    startIcon={<ContentCopyIcon/>}
                                                    disabled={shownCandidates.length === 0}
                                                    onClick={copyCandidatesAsUrls}
                                                    sx={{flexShrink: 0}}
                                                >
                                                    Copy to clipboard
                                                </Button>
                                            </span>
                                        </Tooltip>
                                    </Stack>
                                </Stack>

                                <Typography variant="caption" color="text.secondary" sx={{display: 'block', mb: 1.5}}>
                                    Ranked by strength of connection to the seed accounts.
                                </Typography>

                                {resultsStale && (
                                    <Alert
                                        severity="info"
                                        sx={{mb: 1.5, py: 0, alignItems: 'center'}}
                                        action={
                                            <Button color="inherit" size="small" disabled={isComputing}
                                                    onClick={runAnalysis}>
                                                {isComputing ? 'Refreshing…' : 'Refresh'}
                                            </Button>
                                        }
                                    >
                                        The seed accounts or weights changed since these candidates were computed.
                                    </Alert>
                                )}

                                {shownCandidates.length === 0 ? (
                                    <Typography color="text.secondary" variant="body2">
                                        {candidates.length === 0
                                            ? 'No connected accounts found. Add more seed accounts or adjust the connection weights.'
                                            : visibleCandidates.length === 0
                                                ? 'All candidates have been dismissed.'
                                                : 'No accounts match the current display filters.'}
                                    </Typography>
                                ) : (
                                    <Stack spacing={0} divider={<Divider/>}>
                                        {shownCandidates.map(candidate => (
                                            <CandidateCard
                                                key={candidate.id}
                                                candidate={candidate}
                                                communityDropdown={communityDropdown}
                                                assignedCommunityTagIds={candidateCommunityTagIdSets[candidate.id] ?? EMPTY_ID_SET}
                                                onAddToKernel={() => addCandidateToKernel(candidate)}
                                                onExclude={() => excludeCandidate(candidate)}
                                                onTagToggle={(tag) => handleCandidateTagToggle(candidate, tag)}
                                                tagDistribution={candidateTagDistributions[candidate.id]}
                                                tagDistributionLoading={!!loadingTagDistributions[candidate.id]}
                                                onTagDistributionOpen={() => loadCandidateTagDistribution(candidate.id)}
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
                                    endIcon={<ExpandMoreIcon sx={{
                                        transform: excludedOpen ? 'rotate(180deg)' : 'none',
                                        transition: 'transform 0.2s'
                                    }}/>}
                                    sx={{color: 'text.secondary'}}
                                >
                                    Dismissed ({excludedAccounts.length})
                                </Button>
                                <Collapse in={excludedOpen} unmountOnExit>
                                    <Box sx={{display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 0.5, pl: 0.5}}>
                                        {excludedAccounts.map(acct => (
                                            <Chip
                                                key={acct.id}
                                                component="a"
                                                label={candidateTitle(acct)}
                                                onDelete={() => restoreCandidate(acct.id)}
                                                deleteIcon={<Tooltip title="Restore"><UndoIcon/></Tooltip>}
                                                clickable
                                                sx={{fontSize: '0.75rem'}}
                                            />
                                        ))}
                                    </Box>
                                </Collapse>
                            </Box>
                        </>
                    )}

                </Stack>
            </div>
        </div>
    );
}
