import React, {useEffect, useRef, useState} from 'react';
import {useLocation, useNavigate, useSearchParams} from "react-router";
import {
    Autocomplete,
    Box,
    Button,
    CircularProgress,
    Collapse,
    Divider,
    Fab,
    FormControl,
    IconButton,
    MenuItem,
    OutlinedInput,
    Paper,
    Select,
    Stack,
    Tooltip,
    Typography,
} from "@mui/material";
import TagFilterBar from "../UIComponents/Tags/TagFilterBar";
import TagSelector from "../UIComponents/Tags/TagSelector";
import {ITagWithType} from "../types/tags";
import SearchIcon from '@mui/icons-material/Search';
import QuestionMarkIcon from '@mui/icons-material/QuestionMark';
import FilterListIcon from '@mui/icons-material/FilterList';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import HistoryIcon from '@mui/icons-material/History';
import CloseIcon from '@mui/icons-material/Close';
import {
    ADVANCED_FILTERS_CONFIG,
    batchAnnotate,
    fetchTagsForSearchResults,
    ISearchQuery,
    SEARCH_MODE_TO_ENTITY,
    SEARCH_MODES,
    searchData,
    SearchResult,
    T_Search_Mode
} from "../services/DataFetcher";
import TopNavBar from "../UIComponents/TopNavBar/TopNavBar";
import {SEARCH_SHORTCUTS} from "../UIComponents/SearchShortcuts";
import {DefaultSearchResults, SEARCH_RESULT_RENDERERS} from "../UIComponents/SearchResults";
import {
    Builder,
    BuilderProps,
    ImmutableTree,
    JsonLogicFunction,
    MuiConfig,
    Query,
    Utils as QbUtils,
    Utils
} from '@react-awesome-query-builder/mui';
import '@react-awesome-query-builder/mui/css/styles.css';
import rison from "rison";
import {removeUndefinedValues} from "../services/utils";
import {useSearchHistory} from "../lib/useSearchHistory";

const InitialConfig = MuiConfig;

const DEFAULT_PAGE_SIZES: Partial<Record<T_Search_Mode, number>> = {
    media: 100,
};
const defaultPageSize = (mode: T_Search_Mode) => DEFAULT_PAGE_SIZES[mode] ?? 20;

const getEmptyTree = (search_mode: T_Search_Mode): ImmutableTree => {
    return QbUtils.loadTree({
        id: QbUtils.uuid(),
        type: "group",
        children1: [
            {
                type: "rule",
                id: QbUtils.uuid(),
                properties: {
                    fieldSrc: "field",
                    field: Object.keys(ADVANCED_FILTERS_CONFIG[search_mode])?.[0],
                    operator: null,
                    value: [""],
                    valueSrc: ["value"]
                }
            }
        ]
    })
};

const parseSearchMode = (raw: string | null): T_Search_Mode => {
    const mode = raw || "accounts";
    return SEARCH_MODES.map(m => m.key).includes(mode) ? mode as T_Search_Mode : "accounts";
};

const parseAdvancedFilters = (raw: string | null): JsonLogicFunction | null => {
    if (!raw) return null;
    try { return rison.decode(raw); } catch { return null; }
};

const parsePageInt = (raw: string | null, fallback: number, min: number): number => {
    const n = parseInt(raw || String(fallback));
    return isNaN(n) || n < min ? fallback : n;
};

const extractQueryFromParams = (searchParams: URLSearchParams): ISearchQuery => {
    const search_mode = parseSearchMode(searchParams.get("sm"));
    const modeDefault = defaultPageSize(search_mode);
    return {
        search_term: searchParams.get("s") || "",
        search_mode,
        advanced_filters: parseAdvancedFilters(searchParams.get("f")),
        page_number: parsePageInt(searchParams.get("p"), 1, 1),
        page_size: parsePageInt(searchParams.get("ps"), modeDefault, 20),
        tag_ids: (searchParams.get("t") || "").split(",").map(Number).filter(n => !isNaN(n) && n > 0),
        tag_filter_mode: (searchParams.get("tm") === "all" ? "all" : "any") as "any" | "all",
    };
};

export default function SearchPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const [searchParams] = useSearchParams();

    const query = extractQueryFromParams(searchParams);

    const [typedSearchTerm, setTypedSearchTerm] = useState(query.search_term || "");
    const [tagFilterObjects, setTagFilterObjects] = useState<ITagWithType[]>([]);
    const [showAdvancedFilters, setShowAdvancedFilters] = useState(!!query.advanced_filters);
    const [advancedFiltersTree, setAdvancedFiltersTree] = useState<ImmutableTree>(() =>
        query.advanced_filters ?
            Utils.Import.loadFromJsonLogic(
                query.advanced_filters,
                {...InitialConfig, fields: ADVANCED_FILTERS_CONFIG[query.search_mode]}
            ) || getEmptyTree(query.search_mode) : getEmptyTree(query.search_mode)
    );
    const [results, setResults] = useState<SearchResult[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [tagsMap, setTagsMap] = useState<Record<number, ITagWithType[]>>({});
    const [taggingMode, setTaggingMode] = useState(false);
    const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
    const [bulkTags, setBulkTags] = useState<ITagWithType[]>([]);
    const abortControllerRef = useRef<AbortController | null>(null);
    const isDropdownOpen = useRef(false);
    const {addSearch, removeSearch, getSuggestions} = useSearchHistory();

    useEffect(() => {
        document.title = query.search_term
            ? `${query.search_term} | Search | Browsing Platform`
            : `Search | Browsing Platform`;
    }, [query.search_term]);

    useEffect(() => {
        // Sync typed term and tree with URL when params change (e.g. back/forward navigation)
        setTypedSearchTerm(query.search_term);
        setAdvancedFiltersTree(
            query.advanced_filters ?
                Utils.Import.loadFromJsonLogic(
                    query.advanced_filters,
                    {...InitialConfig, fields: ADVANCED_FILTERS_CONFIG[query.search_mode]}
                ) || getEmptyTree(query.search_mode) : getEmptyTree(query.search_mode)
        );

        // Cancel previous in-flight request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        const controller = new AbortController();
        abortControllerRef.current = controller;
        setIsLoading(true);
        setTagsMap({});
        searchData(query, {signal: controller.signal}).then(results => {
            setResults(results);
            setIsLoading(false);
            abortControllerRef.current = null;
            const ids = results.map(r => r.id).filter((id): id is number => id != null);
            if (ids.length > 0) {
                fetchTagsForSearchResults(query.search_mode, ids).then(setTagsMap);
            }
        }).catch((e: any) => {
            if (e.name !== "AbortError") {
                setIsLoading(false);
                abortControllerRef.current = null;
            }
        });
    }, [searchParams]);

    const encodeQueryToParams = (q: ISearchQuery) => {
        const params = new URLSearchParams();
        if (q.search_term) {
            params.append("s", q.search_term);
        }
        const defaultFilters = QbUtils.Export.jsonLogicFormat(getEmptyTree(q.search_mode), {
            ...InitialConfig,
            fields: ADVANCED_FILTERS_CONFIG[q.search_mode]
        }).logic;
        const currentFilters = q.advanced_filters || null;
        if (currentFilters && JSON.stringify(currentFilters) !== JSON.stringify(defaultFilters)) {
            params.append("f", rison.encode(removeUndefinedValues(currentFilters)));
        }
        if (q.page_number && q.page_number > 1) {
            params.append("p", q.page_number.toString());
        }
        if (q.page_size && q.page_size !== defaultPageSize(q.search_mode)) {
            params.append("ps", q.page_size.toString());
        }
        if (q.search_mode && q.search_mode !== "accounts") {
            params.append("sm", q.search_mode);
        }
        if (q.tag_ids && q.tag_ids.length > 0) {
            params.append("t", q.tag_ids.join(","));
        }
        if (q.tag_ids && q.tag_ids.length > 1 && q.tag_filter_mode && q.tag_filter_mode !== "any") {
            params.append("tm", q.tag_filter_mode);
        }
        const newSearch = params.toString()
            .replaceAll("%28", "(")
            .replaceAll("%29", ")")
            .replaceAll("%27", "'")
            .replaceAll("%3A", ":")
            .replaceAll("%3D", "=")
            .replaceAll("%21", "!")
            .replaceAll("%2C", ",")
            .replaceAll("%3C", "<")
            .replaceAll("%3E", ">");
        // Don't navigate (and thus don't abort the in-flight request) if params haven't changed
        if (newSearch === searchParams.toString()) return;
        navigate({pathname: location.pathname, search: newSearch}, {replace: true});
    };

    const toggleTaggingMode = () => setTaggingMode(prev => {
        if (prev) {
            setSelectedIds(new Set());
            setBulkTags([]);
        }
        return !prev;
    });

    const toggleSelected = (id: number) => setSelectedIds(prev => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id); else next.add(id);
        return next;
    });

    const performSearch = (overrides?: Partial<ISearchQuery>) => {
        const filters = QbUtils.Export.jsonLogicFormat(advancedFiltersTree, {
            ...InitialConfig,
            fields: ADVANCED_FILTERS_CONFIG[query.search_mode]
        }).logic ?? null;
        encodeQueryToParams({
            ...query,
            search_term: typedSearchTerm || "",
            advanced_filters: filters,
            page_number: 1,
            ...overrides,
        });
    };

    const onAdvancedFiltersChange = (immutableTree: ImmutableTree) => {
        setAdvancedFiltersTree(immutableTree);
    };

    const onShortcutChange = (newLogic: JsonLogicFunction | null) => {
        const modeConfig = {...InitialConfig, fields: ADVANCED_FILTERS_CONFIG[query.search_mode]};
        const newTree = newLogic
            ? Utils.Import.loadFromJsonLogic(newLogic, modeConfig) || getEmptyTree(query.search_mode)
            : getEmptyTree(query.search_mode);
        setAdvancedFiltersTree(newTree);
        encodeQueryToParams({
            ...query,
            search_term: typedSearchTerm || "",
            advanced_filters: newLogic,
            page_number: 1,
        });
    };

    const SearchShortcuts = SEARCH_SHORTCUTS[query.search_mode];

    const renderAdvancedFiltersBuilder = (props: BuilderProps) => (
        <div className="query-builder-container" style={{padding: "10px"}}>
            <div className="query-builder qb-lite">
                <Builder {...props} />
            </div>
        </div>
    );

    return <div className={"page-wrap"}>
        <TopNavBar>
            Search Archives
        </TopNavBar>
        <div className={"page-content content-wrap"}>
            <Stack gap={2} sx={{width: '100%'}} divider={<Divider orientation="horizontal" flexItem/>}>
                {/* Search Bar */}
                <Box sx={{mb: 2}}>
                    <Stack direction="row" spacing={2}>
                        <Autocomplete
                            freeSolo
                            autoHighlight={false}
                            options={getSuggestions(query.search_mode, typedSearchTerm)}
                            inputValue={typedSearchTerm}
                            onInputChange={(_, value, reason) => {
                                if (reason !== 'reset') setTypedSearchTerm(value);
                            }}
                            onChange={(_, value) => {
                                debugger;
                                if (typeof value === 'string' && value) {
                                    addSearch(query.search_mode, value);
                                    performSearch({search_term: value});
                                }
                            }}
                            onOpen={() => { isDropdownOpen.current = true; }}
                            onClose={() => { isDropdownOpen.current = false; }}
                            filterOptions={x => x}
                            renderOption={(props, option) => (
                                <Box component="li" {...props}
                                     sx={{display: 'flex', alignItems: 'center', gap: 1, pr: 0.5}}>
                                    <Box sx={{
                                        flex: 1,
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap'
                                    }}>
                                        {option}
                                    </Box>
                                    <HistoryIcon fontSize="small" sx={{color: 'text.disabled', flexShrink: 0}}/>
                                    <Tooltip title={"Remove from Search History"} arrow disableInteractive>
                                        <IconButton
                                            size="small"
                                            onClick={e => {
                                                e.preventDefault();
                                                e.stopPropagation();
                                                removeSearch(query.search_mode, option);
                                            }}
                                            sx={{flexShrink: 0, p: 0.25}}
                                        >
                                            <CloseIcon sx={{fontSize: '0.9rem'}}/>
                                        </IconButton>
                                    </Tooltip>
                                </Box>
                            )}
                            sx={{flex: 1}}
                            renderInput={(params) => (
                                <OutlinedInput
                                    {...params.InputProps}
                                    inputProps={params.inputProps}
                                    onKeyDown={e => {
                                        if (e.key === 'Enter' && (!isDropdownOpen.current || typedSearchTerm === "")) {
                                            if (typedSearchTerm !== null && typedSearchTerm !== undefined) {
                                                addSearch(query.search_mode, typedSearchTerm);
                                            }
                                            performSearch();
                                        }
                                    }}
                                    placeholder="Search..."
                                    sx={{
                                        width: '100%',
                                        '& .MuiOutlinedInput-input': {
                                            width: 'calc(100% - 200px)',
                                        }
                                    }}
                                    size="small"
                                    endAdornment={
                                        <Stack direction="row" gap={2} alignItems="center">
                                            <Tooltip title={"Boolean Search Syntax Explainer"} arrow disableInteractive>
                                                <Fab
                                                    color={"info"}
                                                    href={"https://dev.mysql.com/doc/refman/8.4/en/fulltext-boolean.html"}
                                                    size={"small"}
                                                    target={"_blank"}
                                                    sx={{width: 24, height: 24, minHeight: 24}}
                                                >
                                                    <QuestionMarkIcon fontSize="small" sx={{fontSize: "1em"}}/>
                                                </Fab>
                                            </Tooltip>
                                            <FormControl variant="standard" sx={{width: "200px"}}>
                                                <Select
                                                    value={query.search_mode}
                                                    onChange={(e) => {
                                                        const newMode = e.target.value as T_Search_Mode;
                                                        setAdvancedFiltersTree(getEmptyTree(newMode));
                                                        setSelectedIds(new Set());
                                                        setBulkTags([]);
                                                        performSearch({
                                                            search_mode: newMode,
                                                            advanced_filters: null,
                                                            page_size: defaultPageSize(newMode),
                                                        });
                                                    }}
                                                    sx={{
                                                        width: "100%",
                                                        '& .MuiSelect-select': {paddingLeft: '8px'},
                                                        '::before': {borderBottom: 'none !important'}
                                                    }}
                                                >
                                                    {SEARCH_MODES.map((mode) => (
                                                        <MenuItem key={mode.key} value={mode.key}>
                                                            {mode.label}
                                                        </MenuItem>
                                                    ))}
                                                </Select>
                                            </FormControl>
                                        </Stack>
                                    }
                                />
                            )}
                        />
                        <Tooltip title="Search" arrow disableInteractive>
                            <IconButton color="primary" sx={{padding: '8px'}} onClick={() => {
                                addSearch(query.search_mode, typedSearchTerm);
                                performSearch();
                            }}>
                                <SearchIcon/>
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Advanced Filtering" arrow disableInteractive>
                            <IconButton
                                color="primary"
                                sx={{padding: '8px'}}
                                onClick={() => setShowAdvancedFilters(prev => !prev)}
                            >
                                <FilterListIcon/>
                            </IconButton>
                        </Tooltip>
                    </Stack>
                </Box>
                {/* Search shortcuts — always-visible, mode-specific quick controls */}
                {(SearchShortcuts || SEARCH_MODE_TO_ENTITY[query.search_mode]) && (
                    <Box>
                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                            {SearchShortcuts
                                ? <SearchShortcuts tree={advancedFiltersTree} onChange={onShortcutChange}/>
                                : <Box/>}
                            {SEARCH_MODE_TO_ENTITY[query.search_mode] && (
                                <Button
                                    size="small"
                                    variant={taggingMode ? 'contained' : 'outlined'}
                                    startIcon={<LocalOfferIcon fontSize="small"/>}
                                    onClick={toggleTaggingMode}
                                    sx={{flexShrink: 0, ml: 2}}
                                >
                                    Tag Mode
                                </Button>
                            )}
                        </Stack>
                    </Box>
                )}
                <Collapse in={showAdvancedFilters} timeout="auto" unmountOnExit>
                    <Stack direction={"column"} gap={1} sx={{width: "100%"}}>
                        <Box onKeyDown={(e: React.KeyboardEvent) => {
                            if (e.key === "Enter") {
                                e.preventDefault();
                                e.stopPropagation();
                                performSearch();
                            }
                        }}>
                            {/* Tag filter bar — hidden for archive_sessions (no tag tables) */}
                            {query.search_mode !== "archive_sessions" && (
                                <Box>
                                    <TagFilterBar
                                        tagIds={query.tag_ids || []}
                                        tagFilterMode={query.tag_filter_mode || "any"}
                                        selectedTagObjects={tagFilterObjects}
                                        onChange={(tagIds, mode, tagObjects) => {
                                            setTagFilterObjects(tagObjects);
                                            encodeQueryToParams({
                                                ...query,
                                                search_term: typedSearchTerm || "",
                                                tag_ids: tagIds,
                                                tag_filter_mode: mode,
                                                page_number: 1,
                                            });
                                        }}
                                    />
                                </Box>
                            )}
                            <Query
                                {...InitialConfig}
                                fields={ADVANCED_FILTERS_CONFIG[query.search_mode]}
                                value={advancedFiltersTree}
                                onChange={onAdvancedFiltersChange}
                                renderBuilder={renderAdvancedFiltersBuilder}
                            />
                        </Box>
                        <Button variant={"contained"} onClick={() => performSearch()}>Apply Filters</Button>
                    </Stack>
                </Collapse>
                {/* Search Results */}
                <Box sx={{minHeight: 200}}>
                    {isLoading ? (
                        <Box sx={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: 200}}>
                            <CircularProgress/>
                        </Box>
                    ) : (() => {
                        const ResultsComponent = SEARCH_RESULT_RENDERERS[query.search_mode] ?? DefaultSearchResults;
                        return <ResultsComponent
                            results={results}
                            tagsMap={tagsMap}
                            selectedIds={selectedIds}
                            onToggleSelected={taggingMode && SEARCH_MODE_TO_ENTITY[query.search_mode] ? toggleSelected : undefined}
                        />;
                    })()}
                </Box>
                {/* Pagination */}
                <Stack direction="row" spacing={2} justifyContent={'center'} alignItems={'center'}>
                    <Button
                        variant={"text"}
                        disabled={query.page_number <= 1}
                        onClick={() => encodeQueryToParams({...query, page_number: query.page_number - 1})}
                    >
                        Previous
                    </Button>
                    <Box>Page {query.page_number}</Box>
                    <Button
                        variant={"text"}
                        onClick={() => encodeQueryToParams({...query, page_number: query.page_number + 1})}
                    >
                        Next
                    </Button>
                </Stack>
            </Stack>
        </div>
        {taggingMode && SEARCH_MODE_TO_ENTITY[query.search_mode] && (
            <Paper
                elevation={6}
                sx={{
                    position: 'fixed', bottom: 0, left: 0, right: 0,
                    p: 2, zIndex: 1300,
                    display: 'flex', alignItems: 'center', gap: 2,
                    borderTop: '1px solid', borderColor: 'divider',
                }}
            >
                <Typography sx={{whiteSpace: 'nowrap'}}>{selectedIds.size} selected</Typography>
                <Box sx={{flex: 1, minWidth: 0}}>
                    <TagSelector selectedTags={bulkTags} onChange={setBulkTags}
                                 entity={SEARCH_MODE_TO_ENTITY[query.search_mode]}/>
                </Box>
                <Button
                    variant="contained"
                    disabled={bulkTags.length === 0 || selectedIds.size === 0}
                    onClick={async () => {
                        const entity = SEARCH_MODE_TO_ENTITY[query.search_mode]!;
                        await batchAnnotate(entity, [...selectedIds], bulkTags.map(t => ({id: t.id})));
                        const ids = results.map(r => r.id).filter((id): id is number => id != null);
                        fetchTagsForSearchResults(query.search_mode, ids).then(setTagsMap);
                        setBulkTags([]);
                    }}
                >
                    Add Tags
                </Button>
                <Button onClick={() => {
                    setSelectedIds(new Set());
                    setBulkTags([]);
                }}>
                    Clear Selection
                </Button>
            </Paper>
        )}
    </div>
}
