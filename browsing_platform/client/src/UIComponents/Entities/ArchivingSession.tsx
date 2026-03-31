import React from 'react';
import {IArchiveSession} from "../../types/entities";
import {
    Box, Button,
    Card,
    CardContent,
    CardHeader,
    Chip,
    Divider,
    IconButton,
    Skeleton,
    Stack, Tooltip,
    Typography
} from "@mui/material";
import {DataGrid} from "@mui/x-data-grid";
import {Download, LocalMovies, Lock} from "@mui/icons-material";
import {anchor_local_static_files} from "../../services/server";
import {EntityViewerConfig} from "./EntitiesViewerConfig";
import {getShareTokenFromHref, SHARE_URL_PARAM} from "../../services/linkSharing";
import LinkIcon from "@mui/icons-material/Link";

interface IProps {
    archiveSession: IArchiveSession,
    viewerConfig?: EntityViewerConfig
}

const isPlayableVideo = (filename?: string) => {
    if (!filename) return false;
    const lower = filename.toLowerCase();
    const noSearch = lower.split('?')[0];
    return noSearch.endsWith('.mp4') || noSearch.endsWith('.ogg') || noSearch.endsWith('.webm');
}

const NoAccessChip = ({label}: { label: string }) => (
    <Chip icon={<Lock/>} label={label} variant="outlined" color="default" size="small"
          sx={{color: 'text.secondary'}}/>
);

export default function ArchiveSessionMetadata({archiveSession, viewerConfig}: IProps) {

    const metadata = archiveSession.metadata || {};
    const rows = Object.entries(metadata).map(([key, value], idx) => ({
        id: idx,
        key,
        value: typeof value === 'object' ? JSON.stringify(value) : String(value)
    }));

    const columns = [
        {field: 'key', headerName: 'Key', flex: 1},
        {field: 'value', headerName: 'Value', flex: 2}
    ];

    const shareToken = getShareTokenFromHref();
    const redacted = archiveSession.attachments_redacted ?? [];
    const recordingsRedacted = redacted.includes('screen_recordings');
    const harRedacted = redacted.includes('har_archives');

    const hasRecordings = (archiveSession.attachments?.screen_recordings?.length ?? 0) > 0 || recordingsRedacted;
    const hasHar = (archiveSession.attachments?.har_archives?.length ?? 0) > 0 || harRedacted;

    return (
        <Stack
            direction={"column"}
            divider={<Divider orientation="horizontal" flexItem/>}
            sx={{width: 600}}
            gap={1}
        >
            <Stack
                direction={"row"}
                alignItems={"center"}
                justifyContent={"space-between"}
                sx={{width: "100%", overflow: 'auto'}}
            >
                <Typography variant={"h6"}>Archiving Session {archiveSession.id}</Typography>
                {!viewerConfig?.all?.hideInnerLinks && (
                    <IconButton
                        color={"primary"}
                        href={"/archive/" + archiveSession.id + (shareToken ? `?${SHARE_URL_PARAM}=${shareToken}` : '')}
                    >
                        <LinkIcon/>
                    </IconButton>
                )}
            </Stack>
            {hasRecordings && (
                <Stack
                    direction={"row"}
                    alignItems={"center"}
                    sx={{minHeight: 60, width: "100%", overflow: 'auto'}}
                >
                    {recordingsRedacted
                        ? <NoAccessChip label="You don't have access to the screen recording(s)"/>
                        : archiveSession.attachments!.screen_recordings.map((sr) => {
                            const resourceUrl = anchor_local_static_files(sr) || undefined;
                            if (isPlayableVideo(sr)) {
                                return <video
                                    key={sr}
                                    src={resourceUrl}
                                    style={{backgroundColor: '#000', maxWidth: 300, maxHeight: 300}}
                                    controls
                                />;
                            } else {
                                return <Card sx={{width: 300}} key={sr}>
                                    <a
                                        title={"download video"}
                                        href={resourceUrl} target={"_blank"}
                                        style={{textDecoration: "none", color: "inherit"}}
                                    >
                                        <CardHeader
                                            avatar={<Skeleton animation="wave" variant="circular" width={40}
                                                              height={40}/>}
                                            title={<Skeleton animation="wave" height={10} width="80%"
                                                             style={{marginBottom: 6}}/>}
                                            subheader={<Skeleton animation="wave" height={10} width="40%"/>}
                                        />
                                        <Skeleton sx={{
                                            height: 190, width: "100%", maxWidth: "100%", cursor: "pointer",
                                            "& > *": {visibility: "visible"}
                                        }} animation="wave" variant="rectangular">
                                            <Stack
                                                direction={"column"} gap={1} alignItems={"center"}
                                                justifyContent={"center"}
                                                sx={{height: '100%', width: '100%'}}
                                            >
                                                <LocalMovies color={"primary"} fontSize="large"/>
                                                <Typography variant={"subtitle2"}>Video Can't Be Played In
                                                    Browser</Typography>
                                                <Stack direction={"row"} gap={1} alignItems={"center"}
                                                       justifyContent={"center"}>
                                                    <Download color={"primary"}/>
                                                    <Typography variant={"body1"}>Click to Download</Typography>
                                                </Stack>
                                            </Stack>
                                        </Skeleton>
                                        <CardContent>
                                            <React.Fragment>
                                                <Skeleton animation="wave" height={10} style={{marginBottom: 6}}/>
                                                <Skeleton animation="wave" height={10} width="80%"/>
                                            </React.Fragment>
                                        </CardContent>
                                    </a>
                                </Card>;
                            }
                        })
                    }
                </Stack>
            )}
            {hasHar && (
                <Stack direction={"row"} alignItems={"center"} gap={1} flexWrap={"wrap"}>
                    {harRedacted
                        ? <NoAccessChip label="You don't have access to the HAR file(s)"/>
                        : archiveSession.attachments!.har_archives.map((har) => {
                            const resourceUrl = anchor_local_static_files(har);
                            const handleDownload = async () => {
                                if (!resourceUrl) return;
                                const res = await fetch(resourceUrl);
                                const blob = await res.blob();
                                const a = document.createElement('a');
                                a.href = URL.createObjectURL(blob);
                                a.download = `archive_session_${archiveSession.id}.har`;
                                a.click();
                                URL.revokeObjectURL(a.href);
                            };
                            return (
                                <Tooltip arrow disableInteractive title={"Download HAR file"}>
                                    <Button
                                        key={har}
                                        onClick={async (e) => {
                                            await handleDownload()
                                            e.preventDefault()
                                        }}
                                        color={"primary"}
                                        variant={"outlined"}
                                        startIcon={<Download/>}
                                    >
                                        HAR
                                    </Button>
                                </Tooltip>
                            );
                        })
                    }
                </Stack>
            )}
            <Box sx={{height: 400, width: "100%", overflowY: 'auto'}}>
                <DataGrid rows={rows} columns={columns} hideFooterPagination hideFooter/>
            </Box>
        </Stack>
    );
}
