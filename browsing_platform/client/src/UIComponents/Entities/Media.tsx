import React from 'react';
import {
    IMediaAndAssociatedEntities,
} from "../../types/entities";
import {Box, CircularProgress, Fade, IconButton, Stack} from "@mui/material";
import SelfContainedPopover from "../SelfContainedComponents/selfContainedPopover";
import ReactJson from "react-json-view";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import LinkIcon from "@mui/icons-material/Link";
import {fetchMediaData, fetchPostData} from "../../services/DataFetcher";
import {anchor_local_static_files} from "../../services/server";

interface IProps {
    media: IMediaAndAssociatedEntities
    mediaStyle?: React.CSSProperties
}

interface IState {
    expandDetails: boolean
    awaitingDetailsFetch: boolean
}


export default class Media extends React.Component <IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            expandDetails: false,
            awaitingDetailsFetch: false
        };
    }

    private fetchPostDetails = async () => {
        const itemId = this.props.media.id;
        if (this.state.awaitingDetailsFetch || itemId === undefined || itemId === null) {
            return;
        }
        this.setState((curr => ({...curr, awaitingDetailsFetch: true})), async () => {
            this.props.media.data = await fetchMediaData(itemId);
            this.setState((curr => ({...curr, awaitingDetailsFetch: false})));
        });
    }

    render() {
        const media = this.props.media;
        let localUrl = anchor_local_static_files(media.local_url) || undefined;
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
                    top: 0,
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
                                        onClick={(e) => this.setState((curr) => ({
                                            ...curr,
                                            expandDetails: !curr.expandDetails
                                        }), async () => {
                                            if (this.state.expandDetails && (media.data === undefined || media.data === null)) {
                                                await this.fetchPostDetails();
                                                popupVisibilitySetter(e, true)
                                            }
                                        })}
                                    >
                                        <MoreHorizIcon/>
                                    </IconButton>
                                )}
                                content={() => (<span>
                                    {
                                        this.state.awaitingDetailsFetch ?
                                            <CircularProgress size={20}/> :
                                            this.props.media.data ?
                                                <ReactJson
                                                    src={media.data}
                                                    enableClipboard={false}
                                                /> :
                                                null
                                    }
                                </span>)}
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
