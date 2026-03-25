import React, {useEffect, useMemo, useState} from 'react';
import {useMatch, useParams, useSearchParams} from "react-router";
import {Box, Button, CircularProgress, Collapse, Divider, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography,} from "@mui/material";
import {IArchiveSession, IExtractedEntitiesNested} from "../types/entities";
import {fetchAccount, fetchArchivingSessionsAccount, fetchRelatedTagStats} from "../services/DataFetcher";
import {ITagStat} from "../types/tags";
import EntitiesViewer from "../UIComponents/Entities/EntitiesViewer";
import TopNavBar from "../UIComponents/TopNavBar/TopNavBar";
import ArchivingSessionsList from "../UIComponents/Entities/ArchivingSessionsList";
import {EntityViewerConfig} from "../UIComponents/Entities/EntitiesViewerConfig";
import LinkSharing from "../UIComponents/LinkSharing/LinkSharing";
import cookie from "js-cookie";
import {getShareTokenFromHref} from "../services/linkSharing";

export default function AccountPage() {
    const {id: idParam, platformId} = useParams();
    const urlMatch = useMatch("/account/url/*");
    const urlParam = urlMatch?.params["*"];
    const [searchParams] = useSearchParams();

    const apiRef: number | string | null = useMemo(() => {
        if (platformId) return `pk/${platformId}`;
        if (urlParam) return `url/${urlParam}`;
        if (idParam) return parseInt(idParam);
        return null;
    }, [idParam, platformId, urlParam]);

    const exportMode = searchParams.get("export") === "1";
    const highlightRelationId = searchParams.get('relation_id') ? parseInt(searchParams.get('relation_id')!) : undefined;
    const shareMode = !!getShareTokenFromHref();

    const showAllPosts = exportMode;
    const hideHeader = exportMode || shareMode;
    const hideInnerLinks = exportMode;
    const disableAnnotator = exportMode || shareMode;
    const preloadMetadata = exportMode;

    const [data, setData] = useState<IExtractedEntitiesNested | null>(null);
    const [loadingData, setLoadingData] = useState(apiRef !== null);
    const [sessions, setSessions] = useState<IArchiveSession[] | null>(null);
    const [loadingSessions, setLoadingSessions] = useState(false);
    const [tagStats, setTagStats] = useState<ITagStat[] | null>(null);
    const [tagStatsExpanded, setTagStatsExpanded] = useState(false);
    const [loadingTagStats, setLoadingTagStats] = useState(false);
    const [dbId, setDbId] = useState<number | null>(typeof apiRef === 'number' ? apiRef : null);

    useEffect(() => {
        if (apiRef === null) return;
        setLoadingData(true);
        setLoadingSessions(true);
        const isByDbId = typeof apiRef === 'number';
        if (isByDbId) {
            setDbId(apiRef);
            fetchArchivingSessionsAccount(apiRef, {}).then(sessions => {
                setSessions(sessions);
                setLoadingSessions(false);
            });
        }
        fetchAccount(apiRef, {
            flattened_entities_transform: {
                strip_raw_data: !preloadMetadata,
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
                const resolvedId = result.accounts?.[0]?.id ?? null;
                setDbId(resolvedId);
                if (resolvedId) {
                    fetchArchivingSessionsAccount(resolvedId, {}).then(sessions => {
                        setSessions(sessions);
                        setLoadingSessions(false);
                    });
                } else {
                    setLoadingSessions(false);
                }
            }
        });
    }, [apiRef]);

    const loadTagStats = () => {
        if (!dbId || loadingTagStats || tagStats !== null) return;
        setLoadingTagStats(true);
        fetchRelatedTagStats(dbId).then(stats => {
            setTagStats(stats);
            setLoadingTagStats(false);
        });
    };

    const handleTagStatsToggle = () => {
        const next = !tagStatsExpanded;
        setTagStatsExpanded(next);
        if (next) loadTagStats();
    };

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
            highlightRelationId={highlightRelationId}
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

    const primaryAccount = data?.accounts?.[0];
    const stableSharePath = primaryAccount?.id_on_platform ? `/account/pk/${primaryAccount.id_on_platform}` : undefined;

    const isLoggedIn = !!(cookie.get("token"));
    return <div className={"page-wrap"}>
        <TopNavBar hideMenuButton={hideHeader}>
            <Stack direction={"row"} alignItems={"center"} justifyContent={"space-between"} gap={1} sx={{width: '100%'}}>
                <Stack direction={"row"} alignItems={"center"} gap={1}>
                    <Typography>Account Data</Typography>
                    {
                        data ?
                            <Typography>{primaryAccount?.display_name || primaryAccount?.url}</Typography> :
                            <CircularProgress color={"primary"} size={"16"}/>
                    }
                </Stack>
                {isLoggedIn && dbId ? <LinkSharing entityType={"account"} entityId={dbId} stableSharePath={stableSharePath}/> : null}
            </Stack>
        </TopNavBar>
        <div className={"page-content content-wrap"}>
            <Stack gap={2} sx={{width: '100%'}} divider={<Divider orientation="horizontal" flexItem/>}>
                {renderData()}
                <ArchivingSessionsList sessions={sessions} loadingSessions={loadingSessions}/>
                {!disableAnnotator && dbId && (
                    <Stack gap={1}>
                        <Button variant="text" size="small" onClick={handleTagStatsToggle} sx={{alignSelf: 'flex-start'}}>
                            {tagStatsExpanded ? "▾" : "▸"} Related Accounts — Tag Distribution
                        </Button>
                        <Collapse in={tagStatsExpanded} unmountOnExit>
                            {loadingTagStats ? <CircularProgress size={20}/> : (
                                tagStats && tagStats.length > 0 ? (
                                    <Table size="small" sx={{maxWidth: 480}}>
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>Tag</TableCell>
                                                <TableCell>Type</TableCell>
                                                <TableCell align="right">Count</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {tagStats.map(s => (
                                                <TableRow key={s.tag_id}>
                                                    <TableCell>{s.tag_name}</TableCell>
                                                    <TableCell>{s.tag_type_name}</TableCell>
                                                    <TableCell align="right">×{s.count}</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                ) : <Typography variant="body2" color="text.secondary">No tag data for related accounts.</Typography>
                            )}
                        </Collapse>
                    </Stack>
                )}
            </Stack>
        </div>
    </div>
}
