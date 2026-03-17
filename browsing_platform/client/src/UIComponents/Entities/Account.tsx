import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {IAccountAndAssociatedEntities, IAccountInteractions, IAccountRelation} from "../../types/entities";
import {
    Button,
    CircularProgress,
    Collapse,
    IconButton,
    List,
    ListItem,
    Paper,
    Stack,
    Tooltip,
    Typography
} from "@mui/material";
import LinkIcon from '@mui/icons-material/Link';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import HistoryIcon from '@mui/icons-material/History';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import Post from "./Post";
import ReactJson from "react-json-view";
import {fetchAccountData, fetchAccountInteractions, fetchAccountRelations} from "../../services/DataFetcher";
import {EntityViewerConfig} from "./EntitiesViewerConfig";
import EntityAnnotator from "./Annotator";
import AccountRelation from "./AccountRelation";
import Comment from "./Comment";
import PostLike from "./PostLike";
import TaggedAccountChip from "./TaggedAccountChip";

import {getShareTokenFromHref, SHARE_URL_PARAM} from "../../services/linkSharing";

const HIGHLIGHT_STYLE: React.CSSProperties = {
    backgroundColor: '#fff8dc',
    borderRadius: 4,
    padding: '2px 4px',
    marginLeft: -4,
};

interface IProps {
    account: IAccountAndAssociatedEntities
    viewerConfig?: EntityViewerConfig
    highlightCommentId?: number
    highlightLikeId?: number
    highlightRelationId?: number
}

export default function Account({account: accountProp, viewerConfig, highlightCommentId, highlightLikeId, highlightRelationId}: IProps) {
    const [account, setAccount] = useState(accountProp);
    const [expandDetails, setExpandDetails] = useState(false);
    const [awaitingDetailsFetch, setAwaitingDetailsFetch] = useState(false);
    const [postsToShow, setPostsToShow] = useState(
        viewerConfig?.account?.postsPageSize || accountProp.account_posts.length || 5
    );

    const [relations, setRelations] = useState<IAccountRelation[] | null>(null);
    const [loadingRelations, setLoadingRelations] = useState(false);
    const [relationsExpanded, setRelationsExpanded] = useState(false);

    const [interactions, setInteractions] = useState<IAccountInteractions | null>(null);
    const [loadingInteractions, setLoadingInteractions] = useState(false);
    const [interactionsExpanded, setInteractionsExpanded] = useState(false);

    const relationRefs = useRef<Map<number, HTMLElement>>(new Map());

    const fetchAccountDetails = async () => {
        const itemId = account.id;
        if (awaitingDetailsFetch || itemId === undefined || itemId === null) return;
        setAwaitingDetailsFetch(true);
        const data = await fetchAccountData(itemId);
        setAccount(curr => ({...curr, data}));
        setAwaitingDetailsFetch(false);
    };

    const toggleDetails = async () => {
        const next = !expandDetails;
        setExpandDetails(next);
        if (next && (account.data === undefined || account.data === null)) {
            await fetchAccountDetails();
        }
    };

    const loadRelations = useCallback(async () => {
        if (loadingRelations || relations !== null || account.id == null) return;
        setLoadingRelations(true);
        const fetched = await fetchAccountRelations(account.id);
        setRelations(fetched);
        setLoadingRelations(false);
    }, [loadingRelations, relations, account.id]);

    const toggleRelations = async () => {
        const next = !relationsExpanded;
        setRelationsExpanded(next);
        if (next && relations === null) await loadRelations();
    };

    const toggleInteractions = async () => {
        const next = !interactionsExpanded;
        setInteractionsExpanded(next);
        if (next && interactions === null && account.id != null) {
            setLoadingInteractions(true);
            const fetched = await fetchAccountInteractions(account.id);
            setInteractions(fetched);
            setLoadingInteractions(false);
        }
    };

    // Auto-expand and load relations if a highlight target is specified
    useEffect(() => {
        if (highlightRelationId) {
            setRelationsExpanded(true);
            loadRelations();
        }
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // Scroll to highlighted relation after load
    useEffect(() => {
        if (highlightRelationId && relations) {
            const el = relationRefs.current.get(highlightRelationId);
            el?.scrollIntoView({behavior: 'smooth', block: 'center'});
        }
    }, [relations, highlightRelationId]);

    const sortedPosts = useMemo(() =>
        [...account.account_posts].sort((a, b) =>
            (new Date(b.publication_date || 0).getTime()) - (new Date(a.publication_date || 0).getTime())
        ), [account.account_posts]);

    const urls = (account.identifiers || []).filter(x => x.startsWith("url_")).map(x => x.split("url_")[1]);
    const shareToken = getShareTokenFromHref();

    return <Paper sx={{padding: '1em'}}>
        <Stack gap={0.5} sx={{height: "100%"}}>
            <Stack gap={1} direction={"row"} alignItems={"center"}>
                <Typography variant={"body1"} sx={{userSelect: "all"}}>{account.url}</Typography>
                {
                    urls.length > 1 ? <Tooltip
                        title={
                            <List>
                                {urls.map((url, i) => <ListItem key={i}>{url}</ListItem>)}
                            </List>
                        }
                        arrow
                    >
                        <span>
                            <IconButton size="small" color={"info"}>
                                <HistoryIcon/>
                            </IconButton>
                        </span>
                    </Tooltip> : null
                }
                {
                    viewerConfig?.all?.hideInnerLinks ? null : <IconButton
                        color={"primary"}
                        href={"/account/" + account.id + (shareToken ? `?${SHARE_URL_PARAM}=${shareToken}` : "")}
                    >
                        <LinkIcon/>
                    </IconButton>
                }
            </Stack>
            {account.display_name ? <Typography variant="h4">{account.display_name}</Typography> : null}
            <Typography variant="caption">{account.bio}</Typography>
            <span>
                <IconButton size="small" color={"primary"} onClick={toggleDetails}>
                    <MoreHorizIcon/>
                </IconButton>
            </span>
            <Collapse in={expandDetails}>
                {
                    awaitingDetailsFetch ?
                        <CircularProgress size={20}/> :
                        account.data ?
                            <ReactJson
                                src={account.data}
                                enableClipboard={false}
                                style={{wordBreak: 'break-word'}}
                            /> :
                            null
                }
            </Collapse>
            {
                viewerConfig?.account?.annotator !== "hide" && <Stack gap={1}>
                    <EntityAnnotator
                        entity={account}
                        entityType={"account"}
                        readonly={viewerConfig?.account?.annotator === "disable"}
                    />
                </Stack>
            }

            {/* Posts section */}
            <Stack direction={"column"} sx={{width: "100%", flexGrow: 1}} gap={1}>
                {
                    sortedPosts
                        .slice(0, postsToShow)
                        .map((p, p_i) => (
                            <React.Fragment key={p_i}>
                                <Post
                                    post={p}
                                    viewerConfig={viewerConfig}
                                    highlightCommentId={highlightCommentId}
                                    highlightLikeId={highlightLikeId}
                                />
                            </React.Fragment>
                        ))
                }
                {
                    viewerConfig?.account?.postsPageSize ?
                        <Button
                            variant="contained"
                            disabled={sortedPosts.length <= postsToShow}
                            onClick={() => setPostsToShow(curr => curr + 5)}
                            onDoubleClick={() => setPostsToShow(sortedPosts.length)}
                        >
                            Load More Posts
                        </Button>
                        : null
                }
            </Stack>

            {/* Account relations section (on-demand) */}
            {viewerConfig?.accountRelation?.display !== 'hide' && account.id != null && (
                <Stack gap={0.5}>
                    <Button
                        size="small"
                        variant="outlined"
                        onClick={toggleRelations}
                        endIcon={relationsExpanded ? <ExpandLessIcon/> : <ExpandMoreIcon/>}
                        disabled={loadingRelations}
                        startIcon={loadingRelations ? <CircularProgress size={14}/> : undefined}
                    >
                        Related Accounts
                    </Button>
                    <Collapse in={relationsExpanded}>
                        {relations && relations.length === 0 && (
                            <Typography variant="caption" color="text.secondary">No relations found</Typography>
                        )}
                        {relations && relations.length > 0 && (
                            <Stack gap={0.5} sx={{mt: 0.5}}>
                                {relations.map((r, i) => (
                                    <div
                                        key={i}
                                        ref={r.id != null ? el => { if (el) relationRefs.current.set(r.id!, el); } : undefined}
                                        style={r.id != null && r.id === highlightRelationId ? HIGHLIGHT_STYLE : undefined}
                                    >
                                        <AccountRelation relation={r} contextAccountId={account.id}/>
                                    </div>
                                ))}
                            </Stack>
                        )}
                    </Collapse>
                </Stack>
            )}

            {/* Account interactions section (on-demand) */}
            {account.id != null && (
                <Stack gap={0.5}>
                    <Button
                        size="small"
                        variant="outlined"
                        onClick={toggleInteractions}
                        endIcon={interactionsExpanded ? <ExpandLessIcon/> : <ExpandMoreIcon/>}
                        disabled={loadingInteractions}
                        startIcon={loadingInteractions ? <CircularProgress size={14}/> : undefined}
                    >
                        Interactions
                    </Button>
                    <Collapse in={interactionsExpanded}>
                        {interactions && (
                            <Stack gap={1} sx={{mt: 0.5}}>
                                {interactions.comments.length > 0 && (
                                    <Stack gap={0.5}>
                                        <Typography variant="caption" color="text.secondary">
                                            Comments ({interactions.comments.length})
                                        </Typography>
                                        {interactions.comments.map((c, i) => <Comment key={i} comment={c}/>)}
                                    </Stack>
                                )}
                                {interactions.likes.length > 0 && (
                                    <Stack gap={0.5}>
                                        <Typography variant="caption" color="text.secondary">
                                            Likes ({interactions.likes.length})
                                        </Typography>
                                        {interactions.likes.map((l, i) => <PostLike key={i} like={l}/>)}
                                    </Stack>
                                )}
                                {interactions.tagged_in.length > 0 && (
                                    <Stack gap={0.5}>
                                        <Typography variant="caption" color="text.secondary">
                                            Tagged in ({interactions.tagged_in.length})
                                        </Typography>
                                        <Stack direction="row" gap={0.5} flexWrap="wrap">
                                            {interactions.tagged_in.map((ta, i) => <TaggedAccountChip key={i} taggedAccount={ta}/>)}
                                        </Stack>
                                    </Stack>
                                )}
                                {interactions.comments.length === 0 && interactions.likes.length === 0 && interactions.tagged_in.length === 0 && (
                                    <Typography variant="caption" color="text.secondary">No interactions found</Typography>
                                )}
                            </Stack>
                        )}
                    </Collapse>
                </Stack>
            )}
        </Stack>
    </Paper>
}
