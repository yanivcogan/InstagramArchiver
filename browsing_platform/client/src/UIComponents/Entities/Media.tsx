import React, {useEffect, useState} from 'react';
import {useLocation, useNavigate} from "react-router";
import {IMediaAndAssociatedEntities,} from "../../types/entities";
import {Box, Button, CircularProgress, Fade, IconButton, Stack, Typography} from "@mui/material";
import SelfContainedPopover from "../SelfContainedComponents/selfContainedPopover";
import ReactJson from "react-json-view";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import LinkIcon from "@mui/icons-material/Link";
import {fetchMediaData, fetchMediaParts} from "../../services/DataFetcher";
import {anchor_local_static_files} from "../../services/server";
import MediaPart from "./MediaPart";
import {EntityViewerConfig} from "./EntitiesViewerConfig";
import EntityAnnotator from "./Annotator";
import {getShareTokenFromHref, SHARE_URL_PARAM} from "../../services/linkSharing";

interface IProps {
    media: IMediaAndAssociatedEntities
    viewerConfig?: EntityViewerConfig
}

export default function Media({media: mediaProp, viewerConfig}: IProps) {
    const [media, setMedia] = useState(mediaProp);
    const [expandDetails, setExpandDetails] = useState(false);
    const [awaitingDetailsFetch, setAwaitingDetailsFetch] = useState(false);

    const fetchDetails = async () => {
        const itemId = media.id;
        if (awaitingDetailsFetch || itemId === undefined || itemId === null) {
            return;
        }
        setAwaitingDetailsFetch(true);
        const data = await fetchMediaData(itemId);
        setMedia(curr => ({...curr, data}));
        setAwaitingDetailsFetch(false);
    };

    const refetchMediaParts = async () => {
        const itemId = media.id;
        if (itemId === undefined || itemId === null) return;
        const media_parts = await fetchMediaParts(itemId);
        setMedia(curr => ({...curr, media_parts}));
    };

    const navigate = useNavigate();
    const location = useLocation();
    const onMediaPage = location.pathname.startsWith('/media/');

    const localUrl = anchor_local_static_files(media.local_url) || undefined;
    const thumbnailUrl = anchor_local_static_files(media.thumbnail_path) || undefined;
    const [thumbnailLoaded, setThumbnailLoaded] = useState(false);
    const [mediaLoaded, setMediaLoaded] = useState(false);
    // Reset loading states when the media source changes
    useEffect(() => { setThumbnailLoaded(false); setMediaLoaded(false); }, [localUrl]);
    // Skip thumbnail phase if no thumbnail available (edge case: pending generation)
    useEffect(() => { if (!thumbnailUrl) setThumbnailLoaded(true); }, [thumbnailUrl]);
    const shareToken = getShareTokenFromHref();

    return <div>
        <Box
            sx={{cursor: onMediaPage ? "default" : "pointer", position: "relative"}}
            onMouseEnter={() => setExpandDetails(true)}
            onMouseLeave={() => setExpandDetails(false)}
            onDoubleClick={() => {
                if (!onMediaPage && media.id !== undefined) {
                    navigate(`/media/${media.id}${shareToken ? `?${SHARE_URL_PARAM}=${shareToken}` : ''}`);
                }
            }}
        >
            {
                media.media_type === "video" ? (
                    // While thumbnail loads: 1:1 grey box. Once thumbnail ready: video with poster takes over.
                    <Box sx={{
                        position: 'relative', display: 'block',
                        '@keyframes mediaPlaceholderPulse': {
                            '0%': {opacity: 1}, '50%': {opacity: 0.4}, '100%': {opacity: 1},
                        },
                        ...viewerConfig?.media?.style,
                        ...(!thumbnailLoaded && {
                            aspectRatio: '1 / 1',
                            backgroundColor: 'action.hover',
                            animation: 'mediaPlaceholderPulse 2s ease-in-out infinite',
                        }),
                    }}>
                        {/* Preloads the thumbnail in the background; onLoad fires when it's ready */}
                        {thumbnailUrl && (
                            <img src={thumbnailUrl} alt="" style={{display: 'none'}}
                                 onLoad={() => setThumbnailLoaded(true)}/>
                        )}
                        {/* Hidden until thumbnail ready so the grey placeholder isn't obscured by a black video */}
                        <video
                            src={localUrl}
                            poster={thumbnailUrl}
                            style={{
                                backgroundColor: '#000',
                                ...viewerConfig?.media?.style,
                                ...(!thumbnailLoaded && {display: 'none'}),
                            }}
                            controls
                            onCanPlay={() => setMediaLoaded(true)}
                        />
                    </Box>
                ) : null
            }
            {
                media.media_type === "image" ? (
                    // While thumbnail loads: 1:1 grey box. Thumbnail then full-res swap in-flow.
                    <Box sx={{
                        position: 'relative', display: 'block',
                        '@keyframes mediaPlaceholderPulse': {
                            '0%': {opacity: 1}, '50%': {opacity: 0.4}, '100%': {opacity: 1},
                        },
                        ...viewerConfig?.media?.style,
                        ...(!thumbnailLoaded && {
                            aspectRatio: '1 / 1',
                            backgroundColor: 'action.hover',
                            animation: 'mediaPlaceholderPulse 2s ease-in-out infinite',
                        }),
                    }}>
                        {/* Thumbnail — in-flow, sizes the box; triggers thumbnailLoaded on load */}
                        {thumbnailUrl && !mediaLoaded && (
                            <img src={thumbnailUrl} alt=""
                                 style={{...viewerConfig?.media?.style, width: '100%', display: 'block'}}
                                 onLoad={() => setThumbnailLoaded(true)}/>
                        )}
                        {/* Full-res — preloads silently while thumbnail shows, then becomes in-flow */}
                        <img
                            src={localUrl}
                            alt="photo"
                            style={{
                                ...viewerConfig?.media?.style,
                                ...(mediaLoaded ? {} : {position: 'absolute', opacity: 0, pointerEvents: 'none', top: 0, left: 0}),
                            }}
                            onLoad={() => setMediaLoaded(true)}
                        />
                    </Box>
                ) : null
            }
            <Box
                sx={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    pointerEvents: "auto",
                }}
            >
                <Fade in={expandDetails} timeout={300}>
                    <Stack
                        direction={"row"}
                        alignItems={"center"}
                        gap={1}
                        sx={{
                            width: "100%",
                            boxSizing: "border-box",
                            backgroundColor: "rgba(0,0,0,0.7)",
                            color: "#fff",
                            p: 2,
                            textAlign: "center",
                        }}
                        className={"media-item-interactions-layout"}
                    >
                        {
                            viewerConfig?.all?.hideInnerLinks ? null : <IconButton
                                color={"primary"}
                                href={"/media/" + media.id + (shareToken ? `?${SHARE_URL_PARAM}=${shareToken}` : '')}
                            >
                                <LinkIcon/>
                            </IconButton>
                        }
                        <span>
                            <SelfContainedPopover
                                trigger={(popupVisibilitySetter) => (
                                    <IconButton
                                        size="small"
                                        color={"primary"}
                                        onClick={async (e) => {
                                            if (media.data === undefined || media.data === null) {
                                                await fetchDetails();
                                            }
                                            popupVisibilitySetter(e, true);
                                        }}
                                    >
                                        <MoreHorizIcon/>
                                    </IconButton>
                                )}
                                content={() => (<span>
                                    {
                                        awaitingDetailsFetch ?
                                            <CircularProgress size={20}/> :
                                            media.data ?
                                                <ReactJson
                                                    src={media.data}
                                                    enableClipboard={false}
                                                    style={{wordBreak: 'break-word'}}
                                                /> :
                                                null
                                    }
                                </span>)}
                                popoverProps={{
                                    anchorOrigin: {
                                        vertical: 'bottom',
                                        horizontal: 'left',
                                    },
                                    transformOrigin: {
                                        vertical: 'top',
                                        horizontal: 'left',
                                    },
                                    sx: {
                                        maxWidth: "90vw",
                                        maxHeight: "60vh"
                                    },
                                }}
                            />
                        </span>
                    </Stack>
                </Fade>
            </Box>
        </Box>
        {
            viewerConfig?.media?.annotator !== "hide" &&
            <EntityAnnotator
                entity={media}
                entityType={"media"}
                readonly={viewerConfig?.media?.annotator === "disable"}
            />
        }
        {
            viewerConfig?.mediaPart.display === "display" ? <Stack direction={"column"} gap={1}>
                <Typography>Segments</Typography>
                {
                    (media.media_parts || []).map(
                        (mediaPart, index: number) => <MediaPart
                            mediaPart={mediaPart}
                            media={media}
                            key={index}
                            refetchMediaParts={refetchMediaParts}
                            onDelete={() => {
                                try {
                                    const parts = [...(media.media_parts || [])];
                                    parts.splice(index, 1);
                                    setMedia(curr => ({...curr, media_parts: parts}));
                                } catch (_) {
                                }
                            }}
                        />
                    )
                }
                <Button
                    variant={"contained"} color={"primary"}
                    onClick={() => {
                        const newPart = {
                            id: undefined,
                            media_id: media.id,
                            crop_area: [0, 100, 0, 100],
                            timestamp_range_start: 0,
                            timestamp_range_end: undefined,
                            notes: "",
                        };
                        setMedia(curr => ({
                            ...curr,
                            media_parts: [...(curr.media_parts || []), newPart]
                        }));
                    }}
                >
                    New Part
                </Button>
            </Stack> : null
        }
    </div>
}
