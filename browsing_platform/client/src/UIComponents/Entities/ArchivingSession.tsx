import React from 'react';
import {IArchiveSession} from "../../types/entities";
import {
    Box,
    Button,
    Card,
    CardContent,
    CardHeader,
    Chip,
    Divider,
    IconButton,
    Menu,
    MenuItem,
    Skeleton,
    Stack,
    Typography
} from "@mui/material";
import {DataGrid} from "@mui/x-data-grid";
import {Download, KeyboardArrowDown, LocalMovies, Lock} from "@mui/icons-material";
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

const DOWNLOADABLE_TYPES = [
    {key: 'screen_shots' as const, label: 'Screenshot'},
    {key: 'wacz_archives' as const, label: 'WACZ Archive'},
    {key: 'har_archives' as const, label: 'HAR Archive'},
    {key: 'hash_files' as const, label: 'Hash File'},
    {key: 'timestamp_files' as const, label: 'Timestamp File'},
    {key: 'other_files' as const, label: 'File'},
];

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

    const [downloadMenuAnchor, setDownloadMenuAnchor] = React.useState<null | HTMLElement>(null);

    const shareToken = getShareTokenFromHref();
    const redacted = archiveSession.attachments_redacted ?? [];
    const recordingsRedacted = redacted.includes('screen_recordings');

    const hasRecordings = (archiveSession.attachments?.screen_recordings?.length ?? 0) > 0 || recordingsRedacted;

    const downloadableItems = DOWNLOADABLE_TYPES.flatMap(({key, label}) => {
        if (redacted.includes(key)) return [];
        const files = archiveSession.attachments?.[key] ?? [];
        return files.map((file, idx) => ({
            id: `${key}-${idx}`,
            label: files.length > 1 ? `${label} ${idx + 1}` : label,
            file,
        }));
    });

    const redactedDownloadableTypes = DOWNLOADABLE_TYPES.filter(({key}) => redacted.includes(key));
    const hasDownloadSection = downloadableItems.length > 0 || redactedDownloadableTypes.length > 0;

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
                                                <Typography variant={"subtitle2"}>
                                                    Video Can't Be Played In Browser
                                                </Typography>
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
            {hasDownloadSection && (
                <Stack direction={"row"} alignItems={"center"} gap={1} flexWrap={"wrap"}>
                    {redactedDownloadableTypes.map(({key, label}) => (
                        <NoAccessChip key={key}
                                      label={`You don't have access to the ${label.toLowerCase()}(s)`}/>
                    ))}
                    {downloadableItems.length > 0 && (
                        <>
                            <Button
                                variant={"outlined"}
                                color={"primary"}
                                startIcon={<Download/>}
                                endIcon={<KeyboardArrowDown/>}
                                onClick={(e) => setDownloadMenuAnchor(e.currentTarget)}
                            >
                                Download
                            </Button>
                            <Menu
                                anchorEl={downloadMenuAnchor}
                                open={Boolean(downloadMenuAnchor)}
                                onClose={() => setDownloadMenuAnchor(null)}
                            >
                                {downloadableItems.map(({id, label, file}) => {
                                    const resourceUrl = anchor_local_static_files(file);
                                    const filename = file.split('/').pop()?.split('?')[0] ?? 'download';
                                    return (
                                        <MenuItem
                                            key={id}
                                            onClick={async () => {
                                                setDownloadMenuAnchor(null);
                                                if (!resourceUrl) return;
                                                const res = await fetch(resourceUrl);
                                                const blob = await res.blob();
                                                const a = document.createElement('a');
                                                a.href = URL.createObjectURL(blob);
                                                a.download = filename;
                                                a.click();
                                                setTimeout(() => URL.revokeObjectURL(a.href), 100);
                                            }}
                                        >
                                            <Download fontSize="small" sx={{mr: 1}}/>
                                            {label}
                                        </MenuItem>
                                    );
                                })}
                            </Menu>
                        </>
                    )}
                </Stack>
            )}
            <Box sx={{height: 400, width: "100%", overflowY: 'auto'}}>
                <DataGrid rows={rows} columns={columns} hideFooterPagination hideFooter/>
            </Box>
        </Stack>
    );
}
