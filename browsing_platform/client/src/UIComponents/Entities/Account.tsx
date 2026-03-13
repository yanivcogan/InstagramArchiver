import React, {useMemo, useState} from 'react';
import {IAccountAndAssociatedEntities} from "../../types/entities";
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
import Post from "./Post";
import ReactJson from "react-json-view";
import {fetchAccountData} from "../../services/DataFetcher";
import {EntityViewerConfig} from "./EntitiesViewerConfig";
import EntityAnnotator from "./Annotator";

import {getShareTokenFromHref, SHARE_URL_PARAM} from "../../services/linkSharing";

interface IProps {
    account: IAccountAndAssociatedEntities
    viewerConfig?: EntityViewerConfig
}

export default function Account({account: accountProp, viewerConfig}: IProps) {
    const [account, setAccount] = useState(accountProp);
    const [expandDetails, setExpandDetails] = useState(false);
    const [awaitingDetailsFetch, setAwaitingDetailsFetch] = useState(false);
    const [postsToShow, setPostsToShow] = useState(
        viewerConfig?.account?.postsPageSize || accountProp.account_posts.length || 5
    );

    const fetchPostDetails = async () => {
        const itemId = account.id;
        if (awaitingDetailsFetch || itemId === undefined || itemId === null) {
            return;
        }
        setAwaitingDetailsFetch(true);
        const data = await fetchAccountData(itemId);
        setAccount(curr => ({...curr, data}));
        setAwaitingDetailsFetch(false);
    };

    const toggleDetails = async () => {
        const next = !expandDetails;
        setExpandDetails(next);
        if (next && (account.data === undefined || account.data === null)) {
            await fetchPostDetails();
        }
    };

    const sortedPosts = useMemo(() =>
        [...account.account_posts].sort((a, b) =>
            (new Date(b.publication_date || 0).getTime()) - (new Date(a.publication_date || 0).getTime())
        ), [account.account_posts]);

    const urls = (account.identifiers || []).filter(x => x.startsWith("url_")).map(x => x.split("url_")[1]);
    const shareToken = getShareTokenFromHref();

    return <Paper sx={{padding: '1em'}}>
        <Stack gap={0.5} sx={{height: "100%"}}>
            <Stack gap={1} direction={"row"} alignItems={"center"}>
                <Typography variant={"body1"}>{account.url}</Typography>
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
            <Stack direction={"column"} sx={{width: "100%", flexGrow: 1}} gap={1}>
                {
                    sortedPosts
                        .slice(0, postsToShow)
                        .map((p, p_i) => {
                            return <React.Fragment key={p_i}>
                                <Post post={p} viewerConfig={viewerConfig}/>
                            </React.Fragment>
                        })
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
        </Stack>
    </Paper>
}
