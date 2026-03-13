import React, {useEffect, useState} from 'react';
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
    const {id: idParam} = useParams();

    const id = idParam === undefined ? null : parseInt(idParam);
    const shareMode = !!getShareTokenFromHref();
    const hideHeader = shareMode;
    const disableAnnotator = shareMode;

    const [data, setData] = useState<IExtractedEntitiesNested | null>(null);
    const [loadingData, setLoadingData] = useState(id !== null);
    const [sessions, setSessions] = useState<IArchiveSession[] | null>(null);
    const [loadingSessions, setLoadingSessions] = useState(false);

    useEffect(() => {
        if (id === null) return;
        setLoadingData(true);
        setLoadingSessions(true);
        fetchMedia(id, {
            flattened_entities_transform: {
                retain_only_media_with_local_files: true,
                local_files_root: null,
            },
            nested_entities_transform: {
                retain_only_posts_with_media: true,
                retain_only_accounts_with_posts: false,
            }
        }).then(data => {
            setData(data);
            setLoadingData(false);
        });
        fetchArchivingSessionsMedia(id, {}).then(sessions => {
            setSessions(sessions);
            setLoadingSessions(false);
        });
    }, [id]);

    const renderData = () => {
        if (loadingData) {
            return <Box sx={{display: "flex", justifyContent: "center", alignItems: "center", height: "100%"}}>
                <CircularProgress/>
            </Box>
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

    const isLoggedIn = !!(cookie.get("token"));
    return <div className={"page-wrap"}>
        <TopNavBar hideMenuButton={hideHeader}>
            <Stack direction={"row"} alignItems={"center"} justifyContent={"space-between"} gap={1} sx={{width: '100%'}}>
                <Stack direction={"row"} alignItems={"center"} gap={1}>
                    <Typography>Media Data</Typography>
                    {
                        data ?
                            <Typography>{data.accounts?.[0].account_posts?.[0]?.post_media?.[0]?.url}</Typography> :
                            <CircularProgress color={"primary"} size={"16"}/>
                    }
                </Stack>
                {isLoggedIn && id ? <LinkSharing entityType={"media"} entityId={id}/> : null}
            </Stack>
        </TopNavBar>
        <div className={"page-content content-wrap"}>
            <Stack gap={2} sx={{width: '100%'}} divider={<Divider orientation="horizontal" flexItem/>}>
                {renderData()}
                <ArchivingSessionsList sessions={sessions} loadingSessions={loadingSessions}/>
            </Stack>
        </div>
    </div>
}
