import React, {useEffect, useState} from 'react';
import TextField from '@mui/material/TextField';
import {CircularProgress, Fab, IconButton, Tooltip, Typography} from "@mui/material";
import {ContentCopy, Share} from "@mui/icons-material";
import server from "../../services/server";
import InputAdornment from "@mui/material/InputAdornment";
import {NoMaxWidthTooltip} from "../StyledComponents/CustomTooltips";
import {SHARE_URL_PARAM} from "../../services/linkSharing";

type E_ENTITY_TYPES = "archiving_session" | "account" | "post" | "media" | "media_part"

interface IProps {
    entityType: E_ENTITY_TYPES,
    entityId: number,
}

export default function LinkSharing({entityType, entityId}: IProps) {
    const [awaitingLinkFetch, setAwaitingLinkFetch] = useState(false);
    const [sharedLink, setSharedLink] = useState<string | null>(null);
    const [generationError, setGenerationError] = useState<string | null>(null);

    const shareLinkFromSuffix = (suffix: string) => {
        const url = new URL(window.location.href);
        url.searchParams.set(SHARE_URL_PARAM, suffix);
        return url.toString();
    };

    useEffect(() => {
        setSharedLink(null);
        setGenerationError(null);
        setAwaitingLinkFetch(true);
        server.get(`share/${entityType}/${entityId}/`).then((response: string | null) => {
            setSharedLink(response ? shareLinkFromSuffix(response) : null);
            setAwaitingLinkFetch(false);
        });
    }, [entityType, entityId]);

    const generateShareLink = async () => {
        setAwaitingLinkFetch(true);
        const response: {
            success: boolean, link_suffix: null | string, error: null | string
        } = await server.post(`share/`, {
            view: true,
            shared_entity: {entity: entityType, entity_id: entityId}
        });
        if (response.success && response.link_suffix) {
            setSharedLink(shareLinkFromSuffix(response.link_suffix));
            setGenerationError(null);
        } else {
            setGenerationError(response.error || "Unknown error");
        }
        setAwaitingLinkFetch(false);
    };

    const copyShareLinkToClipboard = () => {
        if (sharedLink) {
            navigator.clipboard.writeText(sharedLink);
            window.alert("Link copied to clipboard!");
        }
    };

    return <NoMaxWidthTooltip
        title={
            awaitingLinkFetch ?
                <CircularProgress size={"20"} color={"primary"}/> :
                sharedLink ?
                    <TextField
                        value={sharedLink}
                        size="small"
                        variant="outlined"
                        slotProps={{
                            htmlInput: {readOnly: true},
                            input: {
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <Tooltip title="Copy">
                                            <IconButton size="small" onClick={copyShareLinkToClipboard}>
                                                <ContentCopy fontSize="small"/>
                                            </IconButton>
                                        </Tooltip>
                                    </InputAdornment>
                                )
                            }
                        }}
                        sx={{
                            padding: 0,
                            background: "white",
                            borderRadius: "inherit",
                            width: `${Math.max(10, sharedLink.length)}ch`
                        }}
                    /> :
                    <Typography variant={"body2"}>Generate shareable link</Typography>
        }
        arrow
    >
        {awaitingLinkFetch ?
            <CircularProgress size={20} color={"primary"}/> :
            <Fab
                size={"small"}
                color={sharedLink ? "success" : "primary"}
                onClick={sharedLink ? copyShareLinkToClipboard : generateShareLink}
            >
                <Share/>
            </Fab>
        }
    </NoMaxWidthTooltip>
}
