import React, {useCallback, useEffect, useRef, useState} from 'react';
import {IComment, IPostAndAssociatedEntities, IPostLike} from "../../types/entities";
import {Button, CircularProgress, Collapse, IconButton, Paper, Stack, Typography} from "@mui/material";
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import Media from "./Media";
import ReactJson from "react-json-view";
import LinkIcon from "@mui/icons-material/Link";
import {fetchPostComments, fetchPostData, fetchPostLikes} from "../../services/DataFetcher";
import {EntityViewerConfig} from "./EntitiesViewerConfig";
import EntityAnnotator from "./Annotator";
import dayjs from "dayjs";
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import TaggedAccountChip from "./TaggedAccountChip";
import Comment from "./Comment";
import PostLike from "./PostLike";

import {getShareTokenFromHref, SHARE_URL_PARAM} from "../../services/linkSharing";

dayjs.extend(utc);
dayjs.extend(timezone);

const HIGHLIGHT_STYLE: React.CSSProperties = {
    backgroundColor: '#fff8dc',
    borderRadius: 4,
    padding: '2px 4px',
    marginLeft: -4,
};

interface IProps {
    post: IPostAndAssociatedEntities
    viewerConfig?: EntityViewerConfig
    highlightCommentId?: number
    highlightLikeId?: number
}

export default function Post({post: postProp, viewerConfig, highlightCommentId, highlightLikeId}: IProps) {
    const [post, setPost] = useState(postProp);
    const [expandDetails, setExpandDetails] = useState(false);
    const [awaitingDetailsFetch, setAwaitingDetailsFetch] = useState(false);

    const preloadedComments = postProp.post_comments.length > 0 ? postProp.post_comments : null;
    const [comments, setComments] = useState<IComment[] | null>(preloadedComments);
    const [loadingComments, setLoadingComments] = useState(false);
    const [commentsLoaded, setCommentsLoaded] = useState(preloadedComments !== null);

    const [likes, setLikes] = useState<IPostLike[] | null>(null);
    const [loadingLikes, setLoadingLikes] = useState(false);
    const [likesLoaded, setLikesLoaded] = useState(false);

    const commentRefs = useRef<Map<number, HTMLElement>>(new Map());
    const likeRefs = useRef<Map<number, HTMLElement>>(new Map());

    const fetchPostDetails = async () => {
        const itemId = post.id;
        if (awaitingDetailsFetch || itemId === undefined || itemId === null) return;
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

    const loadComments = useCallback(async () => {
        if (loadingComments || commentsLoaded || post.id == null) return;
        setLoadingComments(true);
        const fetched = await fetchPostComments(post.id);
        setComments(fetched);
        setCommentsLoaded(true);
        setLoadingComments(false);
    }, [loadingComments, commentsLoaded, post.id]);

    const loadLikes = useCallback(async () => {
        if (loadingLikes || likesLoaded || post.id == null) return;
        setLoadingLikes(true);
        const fetched = await fetchPostLikes(post.id);
        setLikes(fetched);
        setLikesLoaded(true);
        setLoadingLikes(false);
    }, [loadingLikes, likesLoaded, post.id]);

    // Auto-load on mount when a highlight target is specified
    useEffect(() => {
        if (highlightCommentId && !commentsLoaded) loadComments();
        if (highlightLikeId && !likesLoaded) loadLikes();
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // Scroll to highlighted comment after load
    useEffect(() => {
        if (highlightCommentId && commentsLoaded) {
            const el = commentRefs.current.get(highlightCommentId);
            el?.scrollIntoView({behavior: 'smooth', block: 'center'});
        }
    }, [commentsLoaded, highlightCommentId]);

    // Scroll to highlighted like after load
    useEffect(() => {
        if (highlightLikeId && likesLoaded) {
            const el = likeRefs.current.get(highlightLikeId);
            el?.scrollIntoView({behavior: 'smooth', block: 'center'});
        }
    }, [likesLoaded, highlightLikeId]);

    const dateRaw = post.publication_date;
    const date = dayjs.utc(dateRaw);
    const dateInUTC = date.utc().format('YYYY-MM-DD HH:mm:ss');
    const dateInGaza = date.tz('Asia/Jerusalem').format('YYYY-MM-DD HH:mm:ss');
    const shareToken = getShareTokenFromHref();

    const taggedAccounts = post.post_tagged_accounts || [];
    const showTaggedAccounts = viewerConfig?.taggedAccount?.display !== 'hide' && taggedAccounts.length > 0;

    return <Paper sx={{padding: '1em', boxSizing: 'border-box', width: '100%'}}>
        <Stack gap={0.5}>
            <Stack gap={1} direction={"row"} alignItems={"center"}>
                <Typography variant={"body1"} sx={{userSelect: "all"}}>{post.url}</Typography>
                {
                    viewerConfig?.all?.hideInnerLinks ? null : <IconButton
                        color={"primary"}
                        href={"/post/" + post.id + (shareToken ? `?${SHARE_URL_PARAM}=${shareToken}` : '')}
                    >
                        <LinkIcon/>
                    </IconButton>
                }
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
            <Typography variant="caption">{dateInUTC} (UTC+0)</Typography>
            <Typography variant="caption">{dateInGaza} (in Gaza)</Typography>
            {post.caption ? <Typography variant="body2">{post.caption}</Typography> : null}

            {showTaggedAccounts && (
                <Stack direction="row" gap={0.5} flexWrap="wrap">
                    {taggedAccounts.map((ta, i) => <TaggedAccountChip key={i} taggedAccount={ta}/>)}
                </Stack>
            )}

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

            {/* Comments */}
            {commentsLoaded && comments && comments.length > 0 && (
                <Stack gap={0.5} sx={{mt: 0.5}}>
                    <Typography variant="caption" color="text.secondary">
                        Comments ({comments.length})
                    </Typography>
                    {comments.map((c, i) => (
                        <div
                            key={i}
                            ref={c.id != null ? el => {
                                if (el) commentRefs.current.set(c.id!, el);
                            } : undefined}
                            style={c.id != null && c.id === highlightCommentId ? HIGHLIGHT_STYLE : undefined}
                        >
                            <Comment comment={c} postId={post.id} shareToken={shareToken}/>
                        </div>
                    ))}
                </Stack>
            )}
            {commentsLoaded && (!comments || comments.length === 0) && (
                <Typography variant="caption" color="text.secondary">No comments</Typography>
            )}
            {!commentsLoaded && post.id != null && (
                <span>
                    <Button
                        size="small"
                        variant="text"
                        onClick={loadComments}
                        disabled={loadingComments}
                        startIcon={loadingComments ? <CircularProgress size={14}/> : undefined}
                    >
                        Load Comments
                    </Button>
                </span>
            )}

            {/* Likes */}
            {likesLoaded && likes && likes.length > 0 && (
                <Stack gap={0.5} sx={{mt: 0.5}}>
                    <Typography variant="caption" color="text.secondary">
                        Likes ({likes.length})
                    </Typography>
                    {likes.map((l, i) => (
                        <div
                            key={i}
                            ref={l.id != null ? el => {
                                if (el) likeRefs.current.set(l.id!, el);
                            } : undefined}
                            style={l.id != null && l.id === highlightLikeId ? HIGHLIGHT_STYLE : undefined}
                        >
                            <PostLike like={l} postId={post.id} shareToken={shareToken}/>
                        </div>
                    ))}
                </Stack>
            )}
            {likesLoaded && (!likes || likes.length === 0) && (
                <Typography variant="caption" color="text.secondary">No likes</Typography>
            )}
            {!likesLoaded && post.id != null && (
                <span>
                    <Button
                        size="small"
                        variant="text"
                        onClick={loadLikes}
                        disabled={loadingLikes}
                        startIcon={loadingLikes ? <CircularProgress size={14}/> : undefined}
                    >
                        Load Likes
                    </Button>
                </span>
            )}
        </Stack>
    </Paper>
}
