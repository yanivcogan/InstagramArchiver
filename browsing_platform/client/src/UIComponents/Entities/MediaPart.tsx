import React from 'react';
import {
    IMedia,
    IMediaPart,
} from "../../types/entities";
import {Box, Button, Card, CardActions, CardContent, CircularProgress, FormControl, Stack} from "@mui/material";

import EditIcon from "@mui/icons-material/Edit";
import SaveIcon from "@mui/icons-material/Save";
import {anchor_local_static_files} from "../../services/server";

interface IProps {
    media: IMedia
    mediaPart: IMediaPart
    mediaStyle?: React.CSSProperties
}

interface IState {
    editing: boolean,
    awaitingSave: boolean
}


export default class MediaPart extends React.Component <IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            editing: props.mediaPart.id === null,
            awaitingSave: false
        };
    }

    renderMediaPartPreview = () => {
        const media = this.props.media;
        let localUrl = anchor_local_static_files(media.local_url) || undefined;
        return <Box
            sx={{cursor: "pointer", position: "relative"}}
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
        </Box>
    }

    render() {
        const { mediaPart } = this.props;
        const { editing, awaitingSave } = this.state;
        return <Card>
            <CardContent>
                <Stack direction={"column"} gap={1}>
                    <FormControl>

                    </FormControl>
                </Stack>
            </CardContent>
            <CardActions>
                {
                    editing ?
                        <Button
                            variant={"contained"} color={"primary"} disabled={awaitingSave}
                            startIcon={awaitingSave ? <CircularProgress size={20}/> : <SaveIcon/>}
                        >
                            Save
                        </Button> :
                        <Button
                            variant={"contained"} color={"success"}
                            onClick={() => this.setState({editing: true})}
                            startIcon={<EditIcon/>}
                        >
                            Edit
                        </Button>
                }
                <Button
                    variant={"contained"} color={"error"}
                    disabled={awaitingSave}
                >
                    Delete
                </Button>
            </CardActions>
        </Card>
    }
}
