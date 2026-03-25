import React, {useEffect, useState} from 'react';
import {useParams} from "react-router";
import {Box, CircularProgress, Divider, Stack, Typography,} from "@mui/material";
import {IArchiveSession, IExtractedEntitiesNested} from "../types/entities";
import {fetchArchivingSession} from "../services/DataFetcher";
import EntitiesViewer from "../UIComponents/Entities/EntitiesViewer";
import TopNavBar from "../UIComponents/TopNavBar/TopNavBar";
import ArchivingSessionsList from "../UIComponents/Entities/ArchivingSessionsList";
import {EntityViewerConfig} from "../UIComponents/Entities/EntitiesViewerConfig";
import cookie from "js-cookie";
import LinkSharing from "../UIComponents/LinkSharing/LinkSharing";
import {getShareTokenFromHref} from "../services/linkSharing";

export default function SessionPage() {
    const {id: idParam} = useParams();

    const id = idParam === undefined ? null : parseInt(idParam);
    const shareMode = !!getShareTokenFromHref();
    const hideHeader = shareMode;

    const [data, setData] = useState<IExtractedEntitiesNested | null>(null);
    const [loadingData, setLoadingData] = useState(id !== null);
    const [fetchError, setFetchError] = useState<string | null>(null);
    const [sessions, setSessions] = useState<IArchiveSession[] | null>(null);

    useEffect(() => {
        if (id === null) return;
        setLoadingData(true);
        setFetchError(null);
        fetchArchivingSession(id, {
            flattened_entities_transform: {
                retain_only_media_with_local_files: true,
                local_files_root: null,
            },
            nested_entities_transform: {
                retain_only_posts_with_media: true,
                retain_only_accounts_with_posts: false,
            }
        }).then(result => {
            setData(result.entities);
            setSessions([result.session]);
            setLoadingData(false);
        }).catch(err => {
            setFetchError(err?.message || 'Failed to load session');
            setLoadingData(false);
        });
    }, [id]);

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
                        style: {maxWidth: '100%', maxHeight: '50vh'},
                    }
                })
            }
        />
    };

    const isLoggedIn = !!(cookie.get("token"));
    return <div className={"page-wrap"}>
        <TopNavBar hideMenuButton={hideHeader}>
            <Stack direction={"row"} alignItems={"center"} justifyContent={"space-between"} gap={1} sx={{width: '100%'}}>
                <Stack direction={"row"} alignItems={"center"} gap={1}>
                    <Typography>Archiving Session Data</Typography>
                    {
                        data ?
                            <Typography>Session #{id}</Typography> :
                            <CircularProgress color={"primary"} size={"16"}/>
                    }
                </Stack>
                {isLoggedIn && id ? <LinkSharing entityType={"archiving_session"} entityId={id}/> : null}
            </Stack>
        </TopNavBar>
        <div className={"page-content content-wrap"}>
            <Stack gap={2} sx={{width: '100%'}} divider={<Divider orientation="horizontal" flexItem/>}>
                {renderData()}
                <ArchivingSessionsList sessions={sessions} loadingSessions={loadingData}/>
            </Stack>
        </div>
    </div>
}
