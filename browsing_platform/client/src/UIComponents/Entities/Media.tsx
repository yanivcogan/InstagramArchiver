import React from 'react';
import {
    MediaAndAssociatedEntities,
} from "../../types/entities";
import {Box} from "@mui/material";
import SelfContainedPopover from "../SelfContainedComponents/selfContainedPopover";
import ReactJson from "react-json-view";

interface IProps {
    media: MediaAndAssociatedEntities
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
        if(localUrl && localUrl.startsWith("local_archive_har")){
            localUrl = localUrl.replace("local_archive_har", "http://127.0.0.1:4444/archives");
        }
        return <SelfContainedPopover
            trigger={(popupVisibilitySetter) => (
                <Box onClick={(e) => popupVisibilitySetter(e, true)} sx={{cursor: "pointer"}}>
                    {
                        media.media_type === "video" ?
                            <video
                                src={localUrl}
                            /> :
                            null
                    }
                    {
                        media.media_type === "image" ?
                            <img
                                src={localUrl}
                                alt={"photo"}
                            /> :
                            null
                    }
                </Box>
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
    }
}
