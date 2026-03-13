import React, {useEffect, useState} from 'react';
import {useParams, useSearchParams} from "react-router";
import {Box, CircularProgress, Divider, Stack, Typography,} from "@mui/material";
import {IArchiveSession, IExtractedEntitiesNested} from "../types/entities";
import {fetchAccount, fetchArchivingSessionsAccount} from "../services/DataFetcher";
import EntitiesViewer from "../UIComponents/Entities/EntitiesViewer";
import TopNavBar from "../UIComponents/TopNavBar/TopNavBar";
import ArchivingSessionsList from "../UIComponents/Entities/ArchivingSessionsList";
import {EntityViewerConfig} from "../UIComponents/Entities/EntitiesViewerConfig";
import LinkSharing from "../UIComponents/LinkSharing/LinkSharing";
import cookie from "js-cookie";
import {getShareTokenFromHref} from "../services/linkSharing";

export default function AccountPage() {
    const {id: idParam} = useParams();
    const [searchParams] = useSearchParams();

    const id = idParam === undefined ? null : parseInt(idParam);
    const exportMode = searchParams.get("export") === "1";
    const shareMode = !!getShareTokenFromHref();

    const showAllPosts = exportMode;
    const hideHeader = exportMode || shareMode;
    const hideInnerLinks = exportMode;
    const disableAnnotator = exportMode || shareMode;
    const preloadMetadata = exportMode;

    const [data, setData] = useState<IExtractedEntitiesNested | null>(null);
    const [loadingData, setLoadingData] = useState(id !== null);
    const [sessions, setSessions] = useState<IArchiveSession[] | null>(null);
    const [loadingSessions, setLoadingSessions] = useState(false);

    useEffect(() => {
        if (id === null) return;
        setLoadingData(true);
        setLoadingSessions(true);
        fetchAccount(id, {
            flattened_entities_transform: {
                strip_raw_data: !preloadMetadata,
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
        fetchArchivingSessionsAccount(id, {}).then(sessions => {
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
                    all: {hideInnerLinks},
                    account: {
                        annotator: disableAnnotator ? "disable" : "show",
                        postsPageSize: showAllPosts ? null : 5,
                    },
                    media: {
                        style: {
                            maxWidth: '100%',
                            maxHeight: '40vh',
                            minHeight: '300px'
                        }
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
                    <Typography>Account Data</Typography>
                    {
                        data ?
                            <Typography>{data.accounts?.[0].display_name || data.accounts?.[0].url}</Typography> :
                            <CircularProgress color={"primary"} size={"16"}/>
                    }
                </Stack>
                {isLoggedIn && id ? <LinkSharing entityType={"account"} entityId={id}/> : null}
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
