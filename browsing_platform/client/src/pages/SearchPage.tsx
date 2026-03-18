import React, {useEffect, useRef, useState} from 'react';
import {useLocation, useNavigate, useSearchParams} from "react-router";
import {
    Box,
    Button,
    Card,
    CardMedia,
    CircularProgress,
    Collapse,
    Divider,
    Fab,
    FormControl,
    IconButton,
    MenuItem,
    OutlinedInput,
    Select,
    Stack,
    Tooltip,
    Typography
} from "@mui/material";
import SearchIcon from '@mui/icons-material/Search';
import QuestionMarkIcon from '@mui/icons-material/QuestionMark';
import FilterListIcon from '@mui/icons-material/FilterList';
import {
    ADVANCED_FILTERS_CONFIG,
    ISearchQuery,
    SEARCH_MODES,
    searchData,
    SearchResult,
    T_Search_Mode
} from "../services/DataFetcher";
import TopNavBar from "../UIComponents/TopNavBar/TopNavBar";
import {SEARCH_SHORTCUTS} from "../UIComponents/SearchShortcuts";
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
import {anchor_local_static_files} from "../services/server";

const InitialConfig = MuiConfig;

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

const extractQueryFromParams = (searchParams: URLSearchParams): ISearchQuery => {
    const search_term = searchParams.get("s") || "";
    let search_mode = searchParams.get("sm") || "accounts";
    if (!SEARCH_MODES.map(m => m.key).includes(search_mode)) {
        search_mode = "accounts";
    }
    const advanced_filters_rison = searchParams.get("f") || null;
    let advanced_filters: JsonLogicFunction | null = null;
    if (advanced_filters_rison) {
        try {
            advanced_filters = rison.decode(advanced_filters_rison);
        } catch (e) {
            advanced_filters = null;
        }
    }
    let page_number = parseInt(searchParams.get("p") || "1");
    page_number = isNaN(page_number) || page_number < 1 ? 1 : page_number;
    let page_size = parseInt(searchParams.get("ps") || "20");
    page_size = isNaN(page_size) || page_size < 20 ? 20 : page_size;
    return {
        search_term,
        advanced_filters,
        page_number,
        page_size,
        search_mode: search_mode as T_Search_Mode,
    };
};

export default function SearchPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const [searchParams] = useSearchParams();

    const query = extractQueryFromParams(searchParams);

    const [typedSearchTerm, setTypedSearchTerm] = useState(query.search_term || "");
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
    const abortControllerRef = useRef<AbortController | null>(null);

    useEffect(() => {
        document.title = `Search | Browsing Platform`;
    }, []);

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
        searchData(query, {signal: controller.signal}).then(results => {
            setResults(results);
            setIsLoading(false);
            abortControllerRef.current = null;
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
        if (q.page_size && q.page_size !== 20) {
            params.append("ps", q.page_size.toString());
        }
        if (q.search_mode && q.search_mode !== "accounts") {
            params.append("sm", q.search_mode);
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
                        <OutlinedInput
                            value={typedSearchTerm || ""}
                            onChange={e => setTypedSearchTerm(e.target.value)}
                            onKeyDown={async e => {
                                if (e.key === 'Enter') {
                                    performSearch();
                                }
                            }}
                            placeholder="Search..."
                            sx={{
                                flex: 1,
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
                                                setAdvancedFiltersTree(getEmptyTree(e.target.value as T_Search_Mode));
                                                performSearch({
                                                    search_mode: e.target.value as T_Search_Mode,
                                                    advanced_filters: null,
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
                        <Tooltip title="Search" arrow disableInteractive>
                            <IconButton color="primary" sx={{padding: '8px'}} onClick={() => performSearch()}>
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
                {SearchShortcuts && (
                    <Box>
                        <SearchShortcuts tree={advancedFiltersTree} onChange={onShortcutChange}/>
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
                    ) : (
                        <Stack spacing={2} divider={<Divider orientation={"horizontal"} flexItem/>}>
                            {results.length === 0 ? (
                                <Box>No results found.</Box>
                            ) : (
                                results.map((result, idx) => (
                                    <a
                                        key={idx}
                                        href={`/${result.page}/${result.id}`}
                                        style={{textDecoration: 'none'}}
                                    >
                                        <Card variant="elevation" elevation={0}>
                                            <Typography variant={"h6"}>{result.title}</Typography>
                                            {result.details && (
                                                <Typography variant={"body2"}>{result.details}</Typography>
                                            )}
                                            <CardMedia>
                                                <Stack direction="row" gap={1}>
                                                    {result.thumbnails?.map((tn, i) => (
                                                        <img
                                                            key={i}
                                                            src={anchor_local_static_files(tn) || undefined}
                                                            alt={`Thumbnail ${i + 1}`}
                                                            style={{maxWidth: '100px', maxHeight: '100px'}}
                                                        />
                                                    ))}
                                                </Stack>
                                            </CardMedia>
                                        </Card>
                                    </a>
                                ))
                            )}
                        </Stack>
                    )}
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
    </div>
}
