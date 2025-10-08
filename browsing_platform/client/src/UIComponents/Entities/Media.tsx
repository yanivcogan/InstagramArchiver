import React from 'react';
import {
    IMediaAndAssociatedEntities,
} from "../../types/entities";
import {Box, Fade, IconButton, Stack} from "@mui/material";
import SelfContainedPopover from "../SelfContainedComponents/selfContainedPopover";
import ReactJson from "react-json-view";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import LinkIcon from "@mui/icons-material/Link";

interface IProps {
    media: IMediaAndAssociatedEntities
    mediaStyle?: React.CSSProperties
}

interface IState {
    expandDetails: boolean
}


export default class Media extends React.Component <IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            expandDetails: false
        };
    }

    render() {
        const media = this.props.media;
        let localUrl = media.local_url;
        if (localUrl && localUrl.startsWith("local_archive_har")) {
            localUrl = localUrl.replace("local_archive_har", "http://127.0.0.1:4444/archives");
        }
        return <Box
            sx={{cursor: "pointer", position: "relative"}}
            onMouseEnter={() => this.setState({expandDetails: true})}
            onMouseLeave={() => this.setState({expandDetails: false})}
        >
            {
                media.media_type === "video" ?
                    <video
                        src={localUrl}
                        style={
                            {
                                backgroundColor: '#000',
                                ...this.props.mediaStyle
                            }
                        }
                        controls
                    /> :
                    null
            }
            {
                media.media_type === "image" ?
                    <img
                        src={localUrl}
                        alt={"photo"}
                        style={this.props.mediaStyle}
                    /> :
                    null
            }
            <Box
                sx={{
                    position: "absolute",
                    bottom: 0,
                    left: 0,
                    width: "100%",
                    pointerEvents: "auto",
                }}
            >
                <Fade in={this.state.expandDetails} timeout={300}>
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
                    >
                        <IconButton
                            color={"primary"}
                            href={"/media/" + media.id}
                        >
                            <LinkIcon/>
                        </IconButton>
                        <span>
                            <SelfContainedPopover
                                trigger={(popupVisibilitySetter) => (
                                    <IconButton
                                        size="small"
                                        color={"primary"}
                                        onClick={(e) => popupVisibilitySetter(e, true)}
                                    >
                                        <MoreHorizIcon/>
                                    </IconButton>
                                )}
                                content={() => (<ReactJson
                                    src={media.data}
                                    enableClipboard={false}
                                />)}
                                popoverProps={
                                    {
                                        anchorOrigin: {
                                            vertical: 'bottom',
                                            horizontal: 'left',
                                        },
                                        transformOrigin: {
                                            vertical: 'top',
                                            horizontal: 'left',
                                        }
                                    }
                                }
                            />
                        </span>
                    </Stack>
                </Fade>
            </Box>
        </Box>
    }
}
