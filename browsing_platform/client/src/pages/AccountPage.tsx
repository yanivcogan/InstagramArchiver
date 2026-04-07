import React, {useEffect, useState} from 'react';
import {useParams, useSearchParams} from "react-router";
import {
    Button,
    CircularProgress,
    Collapse,
    IconButton,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    Tooltip,
    Typography,
} from "@mui/material";
import GridOnIcon from '@mui/icons-material/GridOn';
import TableRowsIcon from "@mui/icons-material/TableRows";
import {fetchAccount, fetchArchivingSessionsAccount, fetchRelatedTagStats} from "../services/DataFetcher";
import {ITagStat} from "../types/tags";
import EntitiesViewer from "../UIComponents/Entities/EntitiesViewer";
import ArchivingSessionsList from "../UIComponents/Entities/ArchivingSessionsList";
import {EntityViewerConfig} from "../UIComponents/Entities/EntitiesViewerConfig";
import LinkSharing from "../UIComponents/LinkSharing/LinkSharing";
import DataLoadGuard from "./DataLoadGuard";
import cookie from "js-cookie";
import {getShareTokenFromHref} from "../services/linkSharing";
import {useEntityApiRef, useEntityPageState} from "./useEntityPageState";
import PageShell, {PageSubtitleLoading} from "./PageShell";

export default function AccountPage() {
    const {id: idParam, platformId} = useParams();
    const [searchParams] = useSearchParams();

    const apiRef = useEntityApiRef("/account/url/*", idParam, platformId);

    const exportMode = searchParams.get("export") === "1";
    const highlightRelationId = searchParams.get('relation_id') ? parseInt(searchParams.get('relation_id')!) : undefined;
    const shareMode = !!getShareTokenFromHref();

    const showAllPosts = exportMode;
    const hideHeader = exportMode || shareMode;
    const hideInnerLinks = exportMode;
    const disableAnnotator = exportMode || shareMode;
    const preloadMetadata = exportMode;

    const [compactMode, setCompactMode] = useState<boolean>(
        () => localStorage.getItem('account_compact_mode') === 'true'
    );

    const toggleCompactMode = () => {
        setCompactMode(prev => {
            const next = !prev;
            localStorage.setItem('account_compact_mode', String(next));
            return next;
        });
    };

    const [tagStats, setTagStats] = useState<ITagStat[] | null>(null);
    const [tagStatsExpanded, setTagStatsExpanded] = useState(false);
    const [loadingTagStats, setLoadingTagStats] = useState(false);

    const {data, loadingData, fetchError, sessions, loadingSessions, dbId} = useEntityPageState(
        apiRef,
        (ref) => fetchAccount(ref, {
            flattened_entities_transform: {
                strip_raw_data: !preloadMetadata,
                retain_only_media_with_local_files: true,
                local_files_root: null,
            },
            nested_entities_transform: {
                retain_only_posts_with_media: true,
                retain_only_accounts_with_posts: false,
            }
        }),
        (id) => fetchArchivingSessionsAccount(id, {}),
        (result) => result.accounts?.[0]?.id ?? null,
        'Failed to load account',
    );

    useEffect(() => {
        if (loadingData) {
            document.title = 'Account - Loading... | Browsing Platform';
        } else {
            const account = data?.accounts?.[0];
            const name = account?.display_name || account?.url;
            document.title = name ? `${name} | Account | Browsing Platform` : 'Account | Browsing Platform';
        }
    }, [loadingData, data]);

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

    const renderData = () => (
        <DataLoadGuard loadingData={loadingData} fetchError={fetchError} data={data}>
            <EntitiesViewer
                entities={data!}
                highlightRelationId={highlightRelationId}
                viewerConfig={
                    new EntityViewerConfig({
                        all: {hideInnerLinks},
                        account: {
                            annotator: disableAnnotator ? "disable" : "show",
                            postsPageSize: showAllPosts ? null : 10,
                        },
                        post: {
                            annotator: "disable",
                            compactMode,
                        },
                        media: {
                            style: {
                                maxWidth: '100%',
                                maxHeight: '40vh',
                                minHeight: '300px'
                            },
                            annotator: "disable",
                        }
                    })
                }
            />
        </DataLoadGuard>
    );

    const primaryAccount = data?.accounts?.[0];
    const stableSharePath = primaryAccount?.id_on_platform ? `/account/pk/${primaryAccount.id_on_platform}` : undefined;
    const isLoggedIn = !!(cookie.get("token"));
    return (
        <PageShell
            hideMenu={hideHeader}
            title="Account Data"
            subtitle={<PageSubtitleLoading data={data}><Typography>{primaryAccount?.display_name || primaryAccount?.url_suffix}</Typography></PageSubtitleLoading>}
            headerRight={
                <Stack direction={"row"} alignItems={"center"} gap={0.5} sx={{marginLeft: 'auto'}}>
                    <Tooltip title={compactMode ? "Detailed view" : "Compact view"} arrow>
                        <IconButton color="inherit" onClick={toggleCompactMode}>
                            {compactMode ? <TableRowsIcon/> : <GridOnIcon/>}
                        </IconButton>
                    </Tooltip>
                    {isLoggedIn && dbId ? <LinkSharing entityType={"account"} entityId={dbId} stableSharePath={stableSharePath}/> : null}
                </Stack>
            }
        >
            {renderData()}
            {!fetchError && <ArchivingSessionsList sessions={sessions} loadingSessions={loadingSessions}/>}
            {!fetchError && !disableAnnotator && dbId && (
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
        </PageShell>
    );
}
