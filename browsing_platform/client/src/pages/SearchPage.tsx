import React from 'react';
import './login/Login.scss';
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
    query: ISearchQuery;
    loadingData: boolean;
    results: SearchResult[]
}

class SearchPage extends React.Component<IProps, IState> {
    constructor(props: IProps) {
        super(props);
        const search_term = this.props.searchParams.get("s") || ""
        let search_mode = this.props.searchParams.get("sm") || "posts";
        if (!SEARCH_MODES.map(m => m.key).includes(search_mode)) {
            search_mode = "posts";
        }
        let page_number = parseInt(this.props.searchParams.get("p") || "1");
        page_number = isNaN(page_number) || page_number < 1 ? 1 : page_number;
        let page_size = parseInt(this.props.searchParams.get("ps") || "20");
        page_size = isNaN(page_size) || page_size < 20 ? 20 : page_size;
        this.state = {
            query: {
                search_term,
                page_number,
                page_size,
                search_mode: search_mode as T_Search_Mode,
            },
            results: [],
            loadingData: false,
        }
    }

    componentDidUpdate() {
    }

    async componentDidMount() {
        await Promise.all([
            this.fetchData(),
        ])
    }

    fetchData = async () => {
        if (this.state.loadingData) {
            return;
        }
        this.setState((curr) => ({...curr, loadingData: true}), async () => {
            const results = await searchData(
                this.state.query,
            )
            this.setState((curr) => ({...curr, results, loadingData: false}))
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
                                value={this.state.query.search_term}
                                onChange={e => this.setState((curr) => ({
                                    ...curr,
                                    query: {...curr.query, search_term: e.target.value}
                                }))}
                                onKeyDown={async e => {
                                    if (e.key === 'Enter') {
                                        await this.fetchData();
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
                                                await this.fetchData()
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
                        {this.state.loadingData ? (
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