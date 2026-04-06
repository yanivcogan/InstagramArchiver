import React, {useEffect, useMemo} from 'react';
import {useParams} from "react-router";
import {CircularProgress, Divider, Stack, Typography,} from "@mui/material";
import {fetchArchivingSessionsMedia, fetchMedia} from "../services/DataFetcher";
import EntitiesViewer from "../UIComponents/Entities/EntitiesViewer";
import TopNavBar from "../UIComponents/TopNavBar/TopNavBar";
import ArchivingSessionsList from "../UIComponents/Entities/ArchivingSessionsList";
import {EntityViewerConfig} from "../UIComponents/Entities/EntitiesViewerConfig";
import cookie from "js-cookie";
import LinkSharing from "../UIComponents/LinkSharing/LinkSharing";
import DataLoadGuard from "./DataLoadGuard";
import {getShareTokenFromHref} from "../services/linkSharing";
import {useEntityPageState} from "./useEntityPageState";

export default function MediaPage() {
    const {id: idParam, platformId} = useParams();

    const apiRef: number | string | null = useMemo(() => {
        if (platformId) return `pk/${platformId}`;
        if (idParam) return parseInt(idParam);
        return null;
    }, [idParam, platformId]);

    const shareMode = !!getShareTokenFromHref();
    const hideHeader = shareMode;
    const disableAnnotator = shareMode;

    const {data, loadingData, fetchError, sessions, loadingSessions, dbId} = useEntityPageState(
        apiRef,
        (ref) => fetchMedia(ref, {
            flattened_entities_transform: {retain_only_media_with_local_files: true, local_files_root: null},
            nested_entities_transform: {retain_only_posts_with_media: true, retain_only_accounts_with_posts: false},
        }),
        (id) => fetchArchivingSessionsMedia(id, {}),
        (result) => result.accounts?.[0]?.account_posts?.[0]?.post_media?.[0]?.id ?? null,
        'Failed to load media',
    );

    useEffect(() => {
        if (loadingData) {
            document.title = 'Media - Loading... | Browsing Platform';
        } else {
            const media = data?.accounts?.[0]?.account_posts?.[0]?.post_media?.[0];
            const author = data?.accounts?.[0];
            const authorName = author?.display_name || author?.url;
            document.title = media
                ? `Media #${media.id} by ${authorName || 'Unknown'} | Browsing Platform`
                : 'Media | Browsing Platform';
        }
    }, [loadingData, data]);

    const renderData = () => (
        <DataLoadGuard loadingData={loadingData} fetchError={fetchError} data={data}>
            <EntitiesViewer
                entities={data!}
                viewerConfig={
                    new EntityViewerConfig({
                        account: {
                            annotator: "disable",
                        },
                        post: {
                            annotator: "disable",
                        },
                        media: {
                            style: {maxWidth: '100%', maxHeight: '75vh'},
                            annotator: disableAnnotator ? "disable" : "show",
                        },
                        mediaPart: {
                            display: "display"
                        }
                    })
                }
            />
        </DataLoadGuard>
    );

    const primaryMedia = data?.accounts?.[0]?.account_posts?.[0]?.post_media?.[0];
    const stableSharePath = primaryMedia?.id_on_platform ? `/media/pk/${primaryMedia.id_on_platform}` : undefined;

    const isLoggedIn = !!(cookie.get("token"));
    return <div className={"page-wrap"}>
        <TopNavBar hideMenuButton={hideHeader}>
            <Stack direction={"row"} alignItems={"center"} justifyContent={"space-between"} gap={1} sx={{width: '100%'}}>
                <Stack direction={"row"} alignItems={"center"} gap={1}>
                    <Typography>Media Data</Typography>
                    {
                        data ?
                            <Typography>{primaryMedia?.url}</Typography> :
                            <CircularProgress color={"primary"} size={"16"}/>
                    }
                </Stack>
                {isLoggedIn && dbId ? <LinkSharing entityType={"media"} entityId={dbId} stableSharePath={stableSharePath}/> : null}
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
