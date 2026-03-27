import React, {useEffect, useMemo, useState} from 'react';
import {useParams} from "react-router";
import {Box, CircularProgress, Divider, Stack, Typography,} from "@mui/material";
import {IArchiveSession, IExtractedEntitiesNested} from "../types/entities";
import {fetchArchivingSessionsMedia, fetchMedia} from "../services/DataFetcher";
import EntitiesViewer from "../UIComponents/Entities/EntitiesViewer";
import TopNavBar from "../UIComponents/TopNavBar/TopNavBar";
import ArchivingSessionsList from "../UIComponents/Entities/ArchivingSessionsList";
import {EntityViewerConfig} from "../UIComponents/Entities/EntitiesViewerConfig";
import cookie from "js-cookie";
import LinkSharing from "../UIComponents/LinkSharing/LinkSharing";
import {getShareTokenFromHref} from "../services/linkSharing";

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
            fetchArchivingSessionsMedia(apiRef, {}).then(sessions => {
                setSessions(sessions);
                setLoadingSessions(false);
            }).catch(() => setLoadingSessions(false));
        }
        fetchMedia(apiRef, {
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
                const resolvedId = result.accounts?.[0]?.account_posts?.[0]?.post_media?.[0]?.id ?? null;
                setDbId(resolvedId);
                if (resolvedId) {
                    fetchArchivingSessionsMedia(resolvedId, {}).then(sessions => {
                        setSessions(sessions);
                        setLoadingSessions(false);
                    }).catch(() => setLoadingSessions(false));
                } else {
                    setLoadingSessions(false);
                }
            }
        }).catch(err => {
            setFetchError(err?.message || 'Failed to load media');
            setLoadingData(false);
            setLoadingSessions(false);
        });
    }, [apiRef]);

    const renderData = () => {
        if (loadingData) {
            return <Box sx={{display: "flex", justifyContent: "center", alignItems: "center", height: "100%"}}>
                <CircularProgress/>
            </Box>
        }
        if (fetchError) {
            return <Typography color="text.secondary">{fetchError}</Typography>
        }
        if (!data) {
            return <div>No data</div>
        }
        return <EntitiesViewer
            entities={data}
            viewerConfig={
                new EntityViewerConfig({
                    media: {
                        style: {maxWidth: '100%', maxHeight: '75vh'},
                        annotator: disableAnnotator ? "disable" : "show",
                    },
                    mediaPart: {display: "display"}
                })
            }
        />
    };

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
