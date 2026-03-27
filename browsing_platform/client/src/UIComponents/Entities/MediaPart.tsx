import React, {useRef, useState} from 'react';
import {IMedia, IMediaPart,} from "../../types/entities";
import {
    Box,
    Button,
    Card,
    CardActions,
    CardContent,
    CircularProgress,
    InputLabel,
    Slider,
    Stack,
    Typography
} from "@mui/material";

import EditIcon from "@mui/icons-material/Edit";
import SaveIcon from "@mui/icons-material/Save";
import {anchor_local_static_files} from "../../services/server";
import {EntityViewerConfig} from "./EntitiesViewerConfig";
import {deleteMediaPart, saveMediaPart} from "../../services/DataSaver";

interface IProps {
    media: IMedia
    mediaPart: IMediaPart
    refetchMediaParts: () => Promise<void>
    onDelete: () => void
    viewerConfig?: EntityViewerConfig
}

export default function MediaPart({media, mediaPart: mediaPartProp, refetchMediaParts, onDelete}: IProps) {
    const [mediaPart, setMediaPart] = useState(mediaPartProp);
    const [editing, setEditing] = useState(mediaPartProp.id === undefined);
    const [awaitingSave, setAwaitingSave] = useState(false);
    const [mediaHeight, setMediaHeight] = useState<number | undefined>(undefined);
    const [mediaRuntime, setMediaRuntime] = useState<number | undefined>(undefined);

    const videoRef = useRef<HTMLVideoElement>(null);
    const imageRef = useRef<HTMLImageElement>(null);

    const handleMediaLoaded = () => {
        if (media.media_type === "video" && videoRef.current) {
            const videoDuration = videoRef.current.duration;
            if (mediaPart.timestamp_range_end === undefined) {
                setMediaPart(curr => ({...curr, timestamp_range_end: videoDuration}));
            }
            setMediaHeight(videoRef.current.clientHeight);
            setMediaRuntime(videoDuration);
        } else if (media.media_type === "image" && imageRef.current) {
            setMediaHeight(imageRef.current.clientHeight);
            setMediaRuntime(undefined);
        }
    };

    const localUrl = anchor_local_static_files(media.local_url) || undefined;

    const renderMediaPartCropped = () => {
        const cropArea = mediaPart.crop_area || [0, 100, 0, 100];
        const cropWidth = 300 * (cropArea[1] - cropArea[0]) / 100;
        const cropHeight = (mediaHeight || 300) * (cropArea[3] - cropArea[2]) / 100;
        const offsetX = 300 * cropArea[0] / 100;
        const offsetY = (mediaHeight || 300) * (100 - cropArea[3]) / 100;
        const containerStyle: React.CSSProperties = {
            width: `${cropWidth}px`,
            height: `${cropHeight}px`,
            overflow: 'hidden',
            position: 'relative'
        };
        const mediaStyle: React.CSSProperties = {
            position: 'absolute',
            left: `-${offsetX}px`,
            top: `-${offsetY}px`,
            width: '300px',
            height: mediaHeight ? `${mediaHeight}px` : 'auto',
            objectFit: 'cover'
        };
        return <Box style={containerStyle}>
            {media.media_type === "video" ? (
                <video
                    ref={videoRef}
                    src={localUrl + "#t=" + (mediaPart.timestamp_range_start || 0) + "," + (mediaPart.timestamp_range_end || '')}
                    style={mediaStyle}
                    width={cropWidth}
                    height={cropHeight}
                    onLoadedMetadata={handleMediaLoaded}
                    controls
                />
            ) : null}
            {media.media_type === "image" ? (
                <img
                    ref={imageRef}
                    src={localUrl}
                    alt={"photo"}
                    style={mediaStyle}
                    width={cropWidth}
                    height={cropHeight}
                    onLoad={handleMediaLoaded}
                />
            ) : null}
        </Box>
    };

    const renderMediaPartCropper = () => {
        return <Stack
            direction={"row"} gap={1}
            sx={{height: `calc(${mediaHeight}px + 2.2em)`}}
        >
            <Stack direction={"column"} gap={1}>
                <Box
                    sx={{
                        cursor: "pointer", position: "relative", overflow: "hidden",
                        "::after": {
                            content: '""',
                            position: 'absolute',
                            top: `${100 - (mediaPart.crop_area?.[3] || 0)}%`,
                            left: `${mediaPart.crop_area?.[0]}%`,
                            height: `${(mediaPart.crop_area?.[3] || 0) - (mediaPart.crop_area?.[2] || 0)}%`,
                            width: `${(mediaPart.crop_area?.[1] || 0) - (mediaPart.crop_area?.[0] || 0)}%`,
                            pointerEvents: 'none',
                            boxShadow: "0 0 0 9999px rgba(0, 100, 200, 0.4)"
                        },
                    }}
                >
                    {
                        media.media_type === "video" ?
                            <video
                                ref={videoRef}
                                src={localUrl}
                                style={{backgroundColor: '#000'}}
                                controls
                                width={300}
                                onLoadedMetadata={handleMediaLoaded}
                            /> :
                            null
                    }
                    {
                        media.media_type === "image" ?
                            <img
                                ref={imageRef}
                                src={localUrl}
                                alt={"photo"}
                                width={300}
                                onLoad={handleMediaLoaded}
                            /> :
                            null
                    }
                </Box>
                <Slider
                    value={[mediaPart.crop_area?.[0] || 0, mediaPart.crop_area?.[1] || 100]}
                    onChange={(_, value) => {
                        const [start, end] = value as number[];
                        setMediaPart(curr => ({
                            ...curr,
                            crop_area: [start, end, curr.crop_area?.[2] ?? 0, curr.crop_area?.[3] ?? 100]
                        }));
                    }}
                    min={0}
                    max={100}
                    orientation={"horizontal"}
                />
            </Stack>
            <Slider
                value={[mediaPart.crop_area?.[2] || 0, mediaPart.crop_area?.[3] || 100]}
                onChange={(_, value) => {
                    const [start, end] = value as number[];
                    setMediaPart(curr => ({
                        ...curr,
                        crop_area: [curr.crop_area?.[0] ?? 0, curr.crop_area?.[1] ?? 100, start, end]
                    }));
                }}
                min={0}
                max={100}
                orientation={"vertical"}
                sx={{height: "calc(100% - 2.2em)"}}
            />
        </Stack>
    };

    return <Card>
        <CardContent>
            <Stack direction={"column"} gap={1}>
                {editing ? renderMediaPartCropper() : renderMediaPartCropped()}
                {
                    media.media_type === "video" &&
                    <Stack>
                        <InputLabel>Time Range</InputLabel>
                        {editing ? <Slider
                                value={[mediaPart.timestamp_range_start || 0, mediaPart.timestamp_range_end || mediaRuntime || 100]}
                                onChange={(_, value) => {
                                    const [start, end] = value as number[];
                                    const seekTimestamp = mediaPart.timestamp_range_start !== start ? start : end;
                                    if (videoRef.current) {
                                        videoRef.current.currentTime = seekTimestamp;
                                    }
                                    setMediaPart(curr => ({
                                        ...curr,
                                        timestamp_range_start: start,
                                        timestamp_range_end: end
                                    }));
                                }}
                                min={0}
                                max={mediaRuntime || 100}
                            /> :
                            <Typography>{mediaPart.timestamp_range_start} - {mediaPart.timestamp_range_end}</Typography>
                        }
                    </Stack>
                }
            </Stack>
        </CardContent>
        <CardActions>
            {
                editing ?
                    <Button
                        variant={"contained"} color={"primary"} disabled={awaitingSave}
                        startIcon={awaitingSave ? <CircularProgress size={20} color={"inherit"}/> : <SaveIcon/>}
                        onClick={async () => {
                            setAwaitingSave(true);
                            await saveMediaPart(mediaPart);
                            await refetchMediaParts();
                            setEditing(false);
                            setAwaitingSave(false);
                        }}
                    >
                        Save
                    </Button> :
                    <Button
                        variant={"contained"} color={"success"}
                        onClick={() => setEditing(true)}
                        startIcon={<EditIcon/>}
                    >
                        Edit
                    </Button>
            }
            <Button
                variant={"contained"}
                color={"error"}
                disabled={awaitingSave}
                onClick={async () => {
                    setAwaitingSave(true);
                    const mediaPartId = mediaPart.id;
                    if (!(mediaPartId === null || mediaPartId === undefined)) {
                        await deleteMediaPart(mediaPartId);
                    }
                    onDelete();
                    setAwaitingSave(false);
                }}
            >
                Delete
            </Button>
        </CardActions>
    </Card>
}
