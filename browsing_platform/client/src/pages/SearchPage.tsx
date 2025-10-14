import React from 'react';
import withRouter, {IRouterProps} from "../services/withRouter";
import {
    Box, Button, Card,
    CircularProgress, Divider, FormControl, IconButton, MenuItem, OutlinedInput, Stack, Typography,
} from "@mui/material";
import SearchIcon from '@mui/icons-material/Search';
import {
    ISearchQuery, SEARCH_MODES, searchData, T_Search_Mode
} from "../UIComponents/Entities/DataFetcher";
import TopNavBar from "../UIComponents/TopNavBar/TopNavBar";
import Select from '@mui/material/Select';

type IProps = {} & IRouterProps;


interface SearchResult {
    page: string;
    id: number
    title: string;
    details?: string;
}

interface IState {
    typedSearchTerm?: string;
    query: ISearchQuery;
    queryPromise: AbortController | null;
    results: SearchResult[]
}

class SearchPage extends React.Component<IProps, IState> {
    constructor(props: IProps) {
        super(props);
        const query = this.extractQueryFromParams();
        this.state = {
            query,
            results: [],
            queryPromise: null,
        }
    }

    componentDidUpdate() {
        const new_query = this.extractQueryFromParams();
        if (JSON.stringify(new_query) !== JSON.stringify(this.state.query)) {
            this.setState((curr) => ({...curr, query: new_query}), async () => {
                await this.fetchData();
            })
        }
    }

    async componentDidMount() {
        await Promise.all([
            this.fetchData(),
        ])
    }

    encodeQueryToParams = (query: ISearchQuery) => {
        const params = new URLSearchParams();
        if (query.search_term) {
            params.append("s", query.search_term);
        }
        if (query.page_number && query.page_number > 1) {
            params.append("p", query.page_number.toString());
        }
        if (query.page_size && query.page_size !== 20) {
            params.append("ps", query.page_size.toString());
        }
        if (query.search_mode && query.search_mode !== "posts") {
            params.append("sm", query.search_mode);
        }
        this.props.navigate({
            pathname: this.props.location.pathname,
            search: params.toString()
        }, {replace: true});
    }

    extractQueryFromParams = (): ISearchQuery => {
        const search_term = this.props.searchParams.get("s") || ""
        let search_mode = this.props.searchParams.get("sm") || "posts";
        if (!SEARCH_MODES.map(m => m.key).includes(search_mode)) {
            search_mode = "posts";
        }
        let page_number = parseInt(this.props.searchParams.get("p") || "1");
        page_number = isNaN(page_number) || page_number < 1 ? 1 : page_number;
        let page_size = parseInt(this.props.searchParams.get("ps") || "20");
        page_size = isNaN(page_size) || page_size < 20 ? 20 : page_size;
        return {
            search_term,
            page_number,
            page_size,
            search_mode: search_mode as T_Search_Mode,
        }
    }

    performSearch = () => {
        this.setState((curr) => ({
                ...curr,
                query: {...curr.query, search_term: curr.typedSearchTerm || ""}
            }),
            () => {
                this.encodeQueryToParams(this.state.query);
            })
    }

    fetchData = async () => {
        if (this.state.queryPromise) {
            // Cancel previous search if possible (requires AbortController in searchData)
            this.state.queryPromise.abort?.();
        }
        const controller = new AbortController();
        const queryPromise = searchData(this.state.query, {signal: controller.signal});
        this.setState((curr) => ({...curr, queryPromise: controller}), async () => {
            try {
                const results = await queryPromise;
                this.setState((curr) => ({...curr, results, loadingData: false, queryPromise: null}));
            } catch (e: any) {
                if (e.name !== "AbortError") {
                    this.setState((curr) => ({...curr, loadingData: false, queryPromise: null}));
                }
            }
        });
    }

    render() {
        return <div className={"page-wrap"}>
            <TopNavBar>
                Post Data
            </TopNavBar>
            <div className={"page-content content-wrap"}>
                <Stack gap={2} sx={{width: '100%'}} divider={<Divider orientation="horizontal" flexItem/>}>
                    {/* Search Bar */}
                    <Box sx={{mb: 2}}>
                        <Stack direction="row" spacing={2}>
                            <OutlinedInput
                                value={
                                    this.state.typedSearchTerm || this.state.query.search_term || ""
                                }
                                onChange={e => this.setState((curr) => ({
                                    ...curr,
                                    typedSearchTerm: e.target.value
                                }))}
                                onKeyDown={async e => {
                                    if (e.key === 'Enter') {
                                        await this.performSearch();
                                    }
                                }}
                                placeholder="Search..."
                                sx={{
                                    flex: 1,
                                    width: '100%',
                                    '& .MuiOutlinedInput-input': {
                                        'width': 'calc(100% - 200px)'
                                    }
                                }}
                                size="small"
                                endAdornment={<FormControl
                                    variant="standard"
                                    sx={{width: "200px"}}
                                >
                                    <Select
                                        value={this.state.query.search_mode}
                                        onChange={(e) => {
                                            this.setState((curr) => ({
                                                ...curr,
                                                query: {...curr.query, search_mode: e.target.value as T_Search_Mode}
                                            }), async () => {
                                                await this.performSearch()
                                            })
                                        }}
                                        sx={{width: "100%"}}
                                    >
                                        {
                                            SEARCH_MODES.map((mode) => (
                                                <MenuItem key={mode.key} value={mode.key}>{mode.label}</MenuItem>
                                            ))
                                        }
                                    </Select>
                                </FormControl>
                                }
                            />
                            <IconButton
                                color="primary"
                                onClick={() => this.fetchData()}
                                sx={{padding: '8px'}}
                            >
                                <SearchIcon/>
                            </IconButton>
                        </Stack>
                    </Box>
                    {/* Search Results */}
                    <Box sx={{minHeight: 200}}>
                        {this.state.queryPromise !== null ? (
                            <Box sx={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: 200}}>
                                <CircularProgress/>
                            </Box>
                        ) : (
                            <Stack
                                spacing={2}
                                divider={<Divider orientation={"horizontal"} flexItem/>}
                            >
                                {this.state.results.length === 0 ? (
                                    <Box>No results found.</Box>
                                ) : (
                                    this.state.results.map((result, idx) => (
                                        <a
                                            key={idx}
                                            href={`/${result.page}/${result.id}`}
                                            style={{
                                                textDecoration: 'none',
                                            }}
                                        >
                                            <Card variant="elevation" elevation={0}>
                                                <Typography variant={"h6"}>
                                                    {result.title}
                                                </Typography>
                                                {result.details && (
                                                    <Typography variant={"body2"}>
                                                        {result.details}
                                                    </Typography>
                                                )}
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
                            disabled={this.state.query.page_number <= 1}
                            onClick={() => {
                                this.setState((curr) => ({
                                    ...curr,
                                    query: {...curr.query, page_number: curr.query.page_number - 1}
                                }), this.fetchData);
                            }}
                        >
                            Previous
                        </Button>
                        <Box>Page {this.state.query.page_number}</Box>
                        <Button
                            variant={"text"}
                            onClick={() => {
                                this.setState((curr) => ({
                                    ...curr,
                                    query: {...curr.query, page_number: curr.query.page_number + 1}
                                }), this.fetchData);
                            }}
                        >
                            Next
                        </Button>
                    </Stack>
                </Stack>
            </div>
        </div>
    }
}

export default withRouter(SearchPage);