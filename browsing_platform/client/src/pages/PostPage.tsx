import React, {useEffect, useMemo, useState} from 'react';
import {useMatch, useParams, useSearchParams} from "react-router";
import {CircularProgress, Divider, Stack, Typography,} from "@mui/material";
import {IArchiveSession, IExtractedEntitiesNested} from "../types/entities";
import {fetchArchivingSessionsPost, fetchPost} from "../services/DataFetcher";
import EntitiesViewer from "../UIComponents/Entities/EntitiesViewer";
import TopNavBar from "../UIComponents/TopNavBar/TopNavBar";
import ArchivingSessionsList from "../UIComponents/Entities/ArchivingSessionsList";
import {EntityViewerConfig} from "../UIComponents/Entities/EntitiesViewerConfig";
import LinkSharing from "../UIComponents/LinkSharing/LinkSharing";
import DataLoadGuard from "./DataLoadGuard";
import cookie from "js-cookie";
import {getShareTokenFromHref} from "../services/linkSharing";

export default function PostPage() {
    const {id: idParam, platformId} = useParams();
    const urlMatch = useMatch("/post/url/*");
    const urlParam = urlMatch?.params["*"];
    const [searchParams] = useSearchParams();

    const apiRef: number | string | null = useMemo(() => {
        if (platformId) return `pk/${platformId}`;
        if (urlParam) return `url/${urlParam}`;
        if (idParam) return parseInt(idParam);
        return null;
    }, [idParam, platformId, urlParam]);

    const highlightCommentId = searchParams.get('comment_id') ? parseInt(searchParams.get('comment_id')!) : undefined;
    const highlightLikeId = searchParams.get('like_id') ? parseInt(searchParams.get('like_id')!) : undefined;
    const shareMode = !!getShareTokenFromHref();
    const hideHeader = shareMode;
    const disableAnnotator = shareMode;

    const [data, setData] = useState<IExtractedEntitiesNested | null>(null);
    const [loadingData, setLoadingData] = useState(apiRef !== null);
    const [fetchError, setFetchError] = useState<string | null>(null);
    const [sessions, setSessions] = useState<IArchiveSession[] | null>(null);
    const [loadingSessions, setLoadingSessions] = useState(false);
    const [dbId, setDbId] = useState<number | null>(typeof apiRef === 'number' ? apiRef : null);

    useEffect(() => {
        if (apiRef === null) return;
        setLoadingData(true);
        setLoadingSessions(true);
        setFetchError(null);
        const isByDbId = typeof apiRef === 'number';
        if (isByDbId) {
            setDbId(apiRef);
            fetchArchivingSessionsPost(apiRef, {}).then(sessions => {
                setSessions(sessions);
                setLoadingSessions(false);
            }).catch(() => setLoadingSessions(false));
        }
        fetchPost(apiRef, {
            flattened_entities_transform: {
                retain_only_media_with_local_files: true,
                local_files_root: null,
            },
            nested_entities_transform: {
                retain_only_posts_with_media: true,
                retain_only_accounts_with_posts: false,
            }
        }).then(result => {
            setData(result);
            setLoadingData(false);
            if (!isByDbId) {
                const resolvedId = result.accounts?.[0]?.account_posts?.[0]?.id ?? null;
                setDbId(resolvedId);
                if (resolvedId) {
                    fetchArchivingSessionsPost(resolvedId, {}).then(sessions => {
                        setSessions(sessions);
                        setLoadingSessions(false);
                    }).catch(() => setLoadingSessions(false));
                } else {
                    setLoadingSessions(false);
                }
            }
        }).catch(err => {
            setFetchError(err?.message || 'Failed to load post');
            setLoadingData(false);
            setLoadingSessions(false);
        });
    }, [apiRef]);

    useEffect(() => {
        if (loadingData) {
            document.title = 'Post - Loading... | Browsing Platform';
        } else {
            const post = data?.accounts?.[0]?.account_posts?.[0];
            const author = data?.accounts?.[0];
            const authorName = author?.display_name || author?.url;
            document.title = post
                ? `Post #${post.id} by ${authorName || 'Unknown'} | Browsing Platform`
                : 'Post | Browsing Platform';
        }
    }, [loadingData, data]);

    const renderData = () => (
        <DataLoadGuard loadingData={loadingData} fetchError={fetchError} data={data}>
            <EntitiesViewer
                entities={data!}
                highlightCommentId={highlightCommentId}
                highlightLikeId={highlightLikeId}
                viewerConfig={
                    new EntityViewerConfig({
                        account: {
                            annotator: "disable"
                        },
                        post: {
                            annotator: disableAnnotator ? "disable" : "show"
                        },
                        media: {
                            annotator: "disable",
                            style: {
                                maxWidth: '100%',
                                maxHeight: '40vh',
                            }
                        }
                    })
                }
            />
        </DataLoadGuard>
    );

    const primaryPost = data?.accounts?.[0]?.account_posts?.[0];
    const stableSharePath = primaryPost?.id_on_platform ? `/post/pk/${primaryPost.id_on_platform}` : undefined;

    const isLoggedIn = !!(cookie.get("token"));
    return <div className={"page-wrap"}>
        <TopNavBar hideMenuButton={hideHeader}>
            <Stack direction={"row"} alignItems={"center"} justifyContent={"space-between"} gap={1} sx={{width: '100%'}}>
                <Stack direction={"row"} alignItems={"center"} gap={1}>
                    <Typography>Post Data</Typography>
                    {
                        data ?
                            <Typography>{primaryPost?.url}</Typography> :
                            <CircularProgress color={"primary"} size={"16"}/>
                    }
                </Stack>
                {isLoggedIn && dbId ? <LinkSharing entityType={"post"} entityId={dbId} stableSharePath={stableSharePath}/> : null}
            </Stack>
        </TopNavBar>
        <div className={"page-content content-wrap"}>
            <Stack gap={2} sx={{width: '100%'}} divider={<Divider orientation="horizontal" flexItem/>}>
                {renderData()}
                {!fetchError && <ArchivingSessionsList sessions={sessions} loadingSessions={loadingSessions}/>}
            </Stack>
        </div>
    </div>
}
