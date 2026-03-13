import React, {useState} from 'react';
import {IPostAndAssociatedEntities} from "../../types/entities";
import {CircularProgress, Collapse, IconButton, Paper, Stack, Typography} from "@mui/material";
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import Media from "./Media";
import ReactJson from "react-json-view";
import LinkIcon from "@mui/icons-material/Link";
import {fetchPostData} from "../../services/DataFetcher";
import {EntityViewerConfig} from "./EntitiesViewerConfig";
import EntityAnnotator from "./Annotator";
import dayjs from "dayjs";
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';

import {getShareTokenFromHref, SHARE_URL_PARAM} from "../../services/linkSharing";

dayjs.extend(utc);
dayjs.extend(timezone);

interface IProps {
    post: IPostAndAssociatedEntities
    viewerConfig?: EntityViewerConfig
}

export default function Post({post: postProp, viewerConfig}: IProps) {
    const [post, setPost] = useState(postProp);
    const [expandDetails, setExpandDetails] = useState(false);
    const [awaitingDetailsFetch, setAwaitingDetailsFetch] = useState(false);

    const fetchPostDetails = async () => {
        const itemId = post.id;
        if (awaitingDetailsFetch || itemId === undefined || itemId === null) {
            return;
        }
        setAwaitingDetailsFetch(true);
        const data = await fetchPostData(itemId);
        setPost(curr => ({...curr, data}));
        setAwaitingDetailsFetch(false);
    };

    const toggleDetails = async () => {
        const next = !expandDetails;
        setExpandDetails(next);
        if (next && (post.data === undefined || post.data === null)) {
            await fetchPostDetails();
        }
    };

    const dateRaw = post.publication_date;
    const date = dayjs.utc(dateRaw);
    const dateInUTC = date.utc().format('YYYY-MM-DD HH:mm:ss');
    const dateInGaza = date.tz('Asia/Jerusalem').format('YYYY-MM-DD HH:mm:ss');
    const shareToken = getShareTokenFromHref();

    return <Paper sx={{padding: '1em', boxSizing: 'border-box', width: '100%'}}>
        <Stack gap={0.5}>
            <Stack gap={1} direction={"row"} alignItems={"center"}>
                <Typography variant={"body1"}>{post.url}</Typography>
                {
                    viewerConfig?.all?.hideInnerLinks ? null : <IconButton
                        color={"primary"}
                        href={"/post/" + post.id + (shareToken ? `?${SHARE_URL_PARAM}=${shareToken}` : '')}
                    >
                        <LinkIcon/>
                    </IconButton>
                }
            </Stack>
            <Typography variant="caption">{dateInUTC} (UTC+0)</Typography>
            <Typography variant="caption">{dateInGaza} (in Gaza)</Typography>
            {post.caption ? <Typography variant="body2">{post.caption}</Typography> : null}
            <span>
                <IconButton size="small" color={"primary"} onClick={toggleDetails}>
                    <MoreHorizIcon/>
                </IconButton>
            </span>
            <Collapse in={expandDetails}>
                {
                    awaitingDetailsFetch ?
                        <CircularProgress size={20}/> :
                        post.data ?
                            <ReactJson
                                src={post.data}
                                enableClipboard={false}
                                style={{wordBreak: 'break-word'}}
                            /> :
                            null
                }
            </Collapse>
            <Stack direction={"row"} useFlexGap={true} gap={1} flexWrap={"wrap"}>
                {post.post_media.map((m, m_i) => <Media media={m} viewerConfig={viewerConfig} key={m_i}/>)}
            </Stack>
            {
                viewerConfig?.post?.annotator !== "hide" ?
                    <EntityAnnotator
                        entity={post}
                        entityType={"post"}
                        readonly={viewerConfig?.post?.annotator === "disable"}
                    /> :
                    null
            }
        </Stack>
    </Paper>
}
