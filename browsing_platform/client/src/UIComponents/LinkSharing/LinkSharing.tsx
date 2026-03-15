import React, {useEffect, useState} from 'react';
import {toast} from "material-react-toastify";
import TextField from '@mui/material/TextField';
import {
    CircularProgress,
    Fab,
    FormControlLabel,
    IconButton,
    Stack,
    Switch,
    Tooltip,
    Typography,
} from "@mui/material";
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

interface ShareLinkInfo {
    suffix: string;
    valid: boolean;
}

export default function LinkSharing({entityType, entityId}: IProps) {
    const [isFetching, setIsFetching] = useState(false);
    const [isTogglingValidity, setIsTogglingValidity] = useState(false);
    const [shareLinkInfo, setShareLinkInfo] = useState<ShareLinkInfo | null>(null);
    const [generationError, setGenerationError] = useState<string | null>(null);

    const shareLinkFromSuffix = (suffix: string) => {
        const url = new URL(window.location.href);
        url.searchParams.set(SHARE_URL_PARAM, suffix);
        return url.toString();
    };

    useEffect(() => {
        setShareLinkInfo(null);
        setGenerationError(null);
        setIsFetching(true);
        server.get(`share/${entityType}/${entityId}/`).then((response: {
            link_suffix: string,
            valid: boolean
        } | null) => {
            setShareLinkInfo(response ? {suffix: response.link_suffix, valid: response.valid} : null);
            setIsFetching(false);
        });
    }, [entityType, entityId]);

    const generateShareLink = async () => {
        setIsFetching(true);
        const response: {
            success: boolean, link_suffix: null | string, error: null | string
        } = await server.post(`share/`, {
            view: true,
            shared_entity: {entity: entityType, entity_id: entityId}
        });
        if (response.success && response.link_suffix) {
            setShareLinkInfo({suffix: response.link_suffix, valid: true});
            setGenerationError(null);
        } else {
            setGenerationError(response.error || "Unknown error");
        }
        setIsFetching(false);
    };

    const copyShareLinkToClipboard = () => {
        if (shareLinkInfo) {
            navigator.clipboard.writeText(shareLinkFromSuffix(shareLinkInfo.suffix));
            toast.success("Link copied to clipboard!");
        }
    };

    const handleToggleValidity = async () => {
        if (!shareLinkInfo) return;
        const newValid = !shareLinkInfo.valid;
        setIsTogglingValidity(true);
        await server.post(`share/${entityType}/${entityId}/valid`, {valid: newValid});
        setShareLinkInfo({...shareLinkInfo, valid: newValid});
        setIsTogglingValidity(false);
    };

    const fabColor = shareLinkInfo
        ? (shareLinkInfo.valid ? "success" : "warning")
        : "primary";

    const tooltipContent = isFetching
        ? <CircularProgress size={20} color="primary"/>
        : shareLinkInfo
            ? <Stack spacing={1}>
                <TextField
                    value={shareLinkFromSuffix(shareLinkInfo.suffix)}
                    size="small"
                    variant="outlined"
                    disabled={!shareLinkInfo.valid}
                    slotProps={{
                        htmlInput: {readOnly: true},
                        input: {
                            endAdornment: (
                                <InputAdornment position="end">
                                    <Tooltip title="Copy">
                                        <IconButton size="small" onClick={copyShareLinkToClipboard} disabled={!shareLinkInfo.valid}>
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
                        width: `${Math.max(10, shareLinkFromSuffix(shareLinkInfo.suffix).length)}ch`,
                    }}
                />
                {isTogglingValidity
                    ? <CircularProgress size={20} color="primary"/>
                    : <FormControlLabel
                        control={
                            <Switch
                                checked={shareLinkInfo.valid}
                                onChange={handleToggleValidity}
                                size="small"
                                color="success"
                            />
                        }
                        label={
                            <Typography variant="body2" color="text.secondary">
                                {shareLinkInfo.valid ? "Active" : "Disabled"}
                            </Typography>
                        }
                    />
                }
            </Stack>
            : <Typography variant="body2" color="text.secondary">Generate shareable link</Typography>;

    return <NoMaxWidthTooltip
        title={tooltipContent}
        arrow
        leaveDelay={400}
        slotProps={{
            tooltip: {
                sx: {
                    bgcolor: 'white',
                    color: 'text.primary',
                    boxShadow: 4,
                    borderRadius: 2,
                    p: 2,
                }
            },
            arrow: {sx: {color: 'white'}},
        }}
    >
        {isFetching ?
            <CircularProgress size={20} color="primary"/> :
            <Fab
                size="small"
                color={fabColor}
                onClick={shareLinkInfo ? copyShareLinkToClipboard : generateShareLink}
            >
                <Share/>
            </Fab>
        }
    </NoMaxWidthTooltip>
}
