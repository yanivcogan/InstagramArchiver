import React, {useEffect} from 'react';
import {useParams, useSearchParams} from "react-router";
import {Typography,} from "@mui/material";
import {fetchArchivingSessionsPost, fetchPost} from "../services/DataFetcher";
import EntitiesViewer from "../UIComponents/Entities/EntitiesViewer";
import ArchivingSessionsList from "../UIComponents/Entities/ArchivingSessionsList";
import {EntityViewerConfig} from "../UIComponents/Entities/EntitiesViewerConfig";
import LinkSharing from "../UIComponents/LinkSharing/LinkSharing";
import DataLoadGuard from "./DataLoadGuard";
import cookie from "js-cookie";
import {getShareTokenFromHref} from "../services/linkSharing";
import {useEntityApiRef, useEntityPageState} from "./useEntityPageState";
import PageShell, {PageSubtitleLoading} from "./PageShell";

export default function PostPage() {
    const {id: idParam, platformId} = useParams();
    const [searchParams] = useSearchParams();

    const apiRef = useEntityApiRef("/post/url/*", idParam, platformId);

    const highlightCommentId = searchParams.get('comment_id') ? parseInt(searchParams.get('comment_id')!) : undefined;
    const highlightLikeId = searchParams.get('like_id') ? parseInt(searchParams.get('like_id')!) : undefined;
    const shareMode = !!getShareTokenFromHref();
    const hideHeader = shareMode;
    const disableAnnotator = shareMode;

    const {data, loadingData, fetchError, sessions, loadingSessions, dbId} = useEntityPageState(
        apiRef,
        (ref) => fetchPost(ref, {
            flattened_entities_transform: {retain_only_media_with_local_files: true, local_files_root: null},
            nested_entities_transform: {retain_only_posts_with_media: true, retain_only_accounts_with_posts: false},
        }),
        (id) => fetchArchivingSessionsPost(id, {}),
        (result) => result.accounts?.[0]?.account_posts?.[0]?.id ?? null,
        'Failed to load post',
    );

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
                                width: '29vw',
                                maxHeight: '29vw'
                            },
                        }
                    })
                }
            />
        </DataLoadGuard>
    );

    const primaryPost = data?.accounts?.[0]?.account_posts?.[0];
    const stableSharePath = primaryPost?.id_on_platform ? `/post/pk/${primaryPost.id_on_platform}` : undefined;
    const isLoggedIn = !!(cookie.get("token"));
    return (
        <PageShell
            hideMenu={hideHeader}
            title="Post Data"
            subtitle={<PageSubtitleLoading data={data}><Typography>{primaryPost?.url}</Typography></PageSubtitleLoading>}
            headerRight={isLoggedIn && dbId ? <LinkSharing entityType={"post"} entityId={dbId} stableSharePath={stableSharePath}/> : undefined}
        >
            {renderData()}
            {!fetchError && <ArchivingSessionsList sessions={sessions} loadingSessions={loadingSessions}/>}
        </PageShell>
    );
}
