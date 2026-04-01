import React, {useCallback, useEffect, useRef, useState} from 'react';
import {IComment, IPostAndAssociatedEntities, IPostAuxiliaryCounts, IPostLike} from "../../types/entities";
import {Box, CircularProgress, Collapse, Link, Paper, Stack, Tab, Tabs, Tooltip, Typography} from "@mui/material";
import Media from "./Media";
import ReactJson from "react-json-view";
import {fetchPostAuxiliaryCounts, fetchPostComments, fetchPostData, fetchPostLikes} from "../../services/DataFetcher";
import {EntityViewerConfig} from "./EntitiesViewerConfig";
import EntityAnnotator from "./Annotator";
import dayjs from "dayjs";
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import TaggedAccountChip from "./TaggedAccountChip";
import Comment from "./Comment";
import PostLike from "./PostLike";

import {getShareTokenFromHref, SHARE_URL_PARAM} from "../../services/linkSharing";
import {ChatBubble, DataObject, Favorite} from "@mui/icons-material";

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
    const [awaitingDetailsFetch, setAwaitingDetailsFetch] = useState(false);

    const preloadedComments = postProp.post_comments.length > 0 ? postProp.post_comments : null;
    const [comments, setComments] = useState<IComment[] | null>(preloadedComments);
    const [loadingComments, setLoadingComments] = useState(false);
    const [commentsLoaded, setCommentsLoaded] = useState(preloadedComments !== null);

    const [likes, setLikes] = useState<IPostLike[] | null>(null);
    const [loadingLikes, setLoadingLikes] = useState(false);
    const [likesLoaded, setLikesLoaded] = useState(false);

    const [auxiliaryCounts, setAuxiliaryCounts] = useState<IPostAuxiliaryCounts | null>(null);

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

    useEffect(() => {
        if (post.id == null) return;
        fetchPostAuxiliaryCounts(post.id)
            .then(counts => setAuxiliaryCounts(counts))
            .catch(() => {});
    }, [post.id]); // eslint-disable-line react-hooks/exhaustive-deps

    const [activeTab, setActiveTab] = useState<'comments' | 'likes' | 'raw' | null>(
        highlightCommentId ? 'comments' : highlightLikeId ? 'likes' : null
    );

    useEffect(() => {
        if (activeTab === 'comments') loadComments();
        if (activeTab === 'likes') loadLikes();
        if (activeTab === 'raw') fetchPostDetails();
    }, [activeTab]); // eslint-disable-line react-hooks/exhaustive-deps

    const dateRaw = post.publication_date;
    const date = dayjs.utc(dateRaw);
    const dateInUTC = date.utc().format('YYYY-MM-DD HH:mm:ss');
    const dateInGaza = date.tz('Asia/Jerusalem').format('YYYY-MM-DD HH:mm:ss');
    const shareToken = getShareTokenFromHref();
    const postHref = "/post/" + post.id + (shareToken ? `?${SHARE_URL_PARAM}=${shareToken}` : '');
    const disablePostLink = viewerConfig?.all?.hideInnerLinks;

    const commentsLabel = auxiliaryCounts != null ? `Comments (${auxiliaryCounts.comments_count})` : "Comments";
    const likesLabel = auxiliaryCounts != null ? `Likes (${auxiliaryCounts.likes_count})` : "Likes";

    const taggedAccounts = post.post_tagged_accounts || [];
    const showTaggedAccounts = viewerConfig?.taggedAccount?.display !== 'hide' && taggedAccounts.length > 0;

    return <Paper sx={{padding: '1em', boxSizing: 'border-box', width: '100%', backgroundColor: '#e8f0ff'}}>
        <Stack gap={0.5}>
            <Stack gap={1} direction={"row"} alignItems={"center"}>
                <Typography variant={"subtitle2"} sx={{userSelect: "all"}} color={"textSecondary"}>{post.url}</Typography>
            </Stack>
            <Tooltip
                title={
                    <Typography variant="caption">{dateInGaza} (in Gaza)</Typography>
                }
                arrow
            >
                {disablePostLink
                    ? <Typography variant="caption" sx={{alignSelf: 'flex-start'}}>{dateInUTC} (UTC+0)</Typography>
                    : <Link color={"primary"} href={postHref} sx={{alignSelf: 'flex-start'}}>
                        <Typography variant="caption">{dateInUTC} (UTC+0)</Typography>
                    </Link>
                }
            </Tooltip>
            {
                viewerConfig?.post?.annotator !== "hide" ?
                    <EntityAnnotator
                        entity={post}
                        entityType={"post"}
                        readonly={viewerConfig?.post?.annotator === "disable"}
                    /> :
                    null
            }
            {post.caption ? <Typography variant="body2">{post.caption}</Typography> : null}

            {showTaggedAccounts && (
                <Stack direction="row" gap={0.5} flexWrap="wrap">
                    {taggedAccounts.map((ta, i) => <TaggedAccountChip key={i} taggedAccount={ta}/>)}
                </Stack>
            )}

            <Stack direction={"row"} useFlexGap={true} gap={1} flexWrap={"wrap"}>
                {post.post_media.map((m, m_i) => <Media media={m} viewerConfig={viewerConfig} key={m_i}/>)}
            </Stack>

            {/* Comments / Likes / Raw Data — tab-toggle panel */}
            <Box>
                <Tabs
                    value={activeTab ?? false}
                    onChange={(_, val) => setActiveTab(val)}
                    variant="scrollable"
                    scrollButtons="auto"
                    sx={{minHeight: 32, '& .MuiTab-root': {minHeight: 32, py: 0.5, textTransform: 'none'}}}
                >
                    {post.id != null && (
                        <Tab
                            value="comments"
                            label={commentsLabel}
                            icon={<ChatBubble/>} iconPosition="start"
                            onClick={() => { if (activeTab === 'comments') setActiveTab(null); }}
                        />
                    )}
                    {post.id != null && (
                        <Tab
                            value="likes"
                            label={likesLabel}
                            icon={<Favorite/>} iconPosition="start"
                            onClick={() => { if (activeTab === 'likes') setActiveTab(null); }}
                        />
                    )}
                    <Tab
                        value="raw"
                        label="Raw Data"
                        icon={<DataObject/>} iconPosition="start"
                        onClick={() => { if (activeTab === 'raw') setActiveTab(null); }}
                    />
                </Tabs>

                <Collapse in={activeTab !== null}>
                    <Box sx={{mt: 1}}>
                        {activeTab === 'comments' && (
                            <>
                                {loadingComments && <CircularProgress size={16}/>}
                                {commentsLoaded && comments && comments.length > 0 && (
                                    <Stack gap={0.5}>
                                        {comments.map((c, i) => (
                                            <div
                                                key={i}
                                                ref={c.id != null ? el => { if (el) commentRefs.current.set(c.id!, el); } : undefined}
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
                            </>
                        )}
                        {activeTab === 'likes' && (
                            <>
                                {loadingLikes && <CircularProgress size={16}/>}
                                {likesLoaded && likes && likes.length > 0 && (
                                    <Stack gap={0.5}>
                                        {likes.map((l, i) => (
                                            <div
                                                key={i}
                                                ref={l.id != null ? el => { if (el) likeRefs.current.set(l.id!, el); } : undefined}
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
                            </>
                        )}
                        {activeTab === 'raw' && (
                            <>
                                {awaitingDetailsFetch && <CircularProgress size={16}/>}
                                {post.data && (
                                    <ReactJson src={post.data} enableClipboard={false} style={{wordBreak: 'break-word'}}/>
                                )}
                            </>
                        )}
                    </Box>
                </Collapse>
            </Box>
        </Stack>
    </Paper>
}
