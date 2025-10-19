import React from 'react';
import {IArchiveSession} from "../../types/entities";
import {
    Box, Card, CardContent, CardHeader, Divider, Fade, IconButton, Stack, Typography,
} from "@mui/material";
import {DataGrid} from "@mui/x-data-grid";
import LinkIcon from "@mui/icons-material/Link";
import SelfContainedPopover from "../SelfContainedComponents/selfContainedPopover";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import ReactJson from "react-json-view";
import {Skeleton} from "@mui/lab";
import {Download, LocalMovies} from "@mui/icons-material";
import {fetchArchivingSessionData, fetchPostData} from "../../services/DataFetcher";

interface IProps {
    session: IArchiveSession,
    mediaStyle?: React.CSSProperties
}

interface IState {
    expandDetails: boolean
    awaitingDetailsFetch: boolean
}


const isPlayableVideo = (filename?: string) => {
    if (!filename) return false;
    const lower = filename.toLowerCase();
    return lower.endsWith('.mp4') || lower.endsWith('.ogg') || lower.endsWith('.webm');
}


export default class ArchiveSessionMetadata extends React.Component <IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            expandDetails: false,
            awaitingDetailsFetch: false
        };
    }

    private fetchPostDetails = async () => {
        const itemId = this.props.session.id;
        if (this.state.awaitingDetailsFetch || itemId === undefined || itemId === null) {
            return;
        }
        this.setState((curr => ({...curr, awaitingDetailsFetch: true})), async () => {
            this.props.session.structures = await fetchArchivingSessionData(itemId);
            this.setState((curr => ({...curr, awaitingDetailsFetch: false})));
        });
    }

    render() {
        const session = this.props.session;
        const metadata = session.metadata || {};
        // Convert metadata object to array of { key, value } for DataGrid
        const rows = Object.entries(metadata).map(([key, value], idx) => ({
            id: idx,
            key,
            value: typeof value === 'object' ? JSON.stringify(value) : String(value)
        }));

        const columns = [
            {field: 'key', headerName: 'Key', flex: 1},
            {field: 'value', headerName: 'Value', flex: 2}
        ];

        return (
            <Stack
                direction={"column"}
                divider={<Divider orientation="horizontal" flexItem/>}
                sx={{width: 600}}
            >
                <Stack
                    direction={"row"}
                    alignItems={"center"}
                    sx={{height: 400, width: "100%", overflow: 'auto'}}
                >
                    {
                        session.attachments?.screen_recordings?.map((sr) => {
                            const resourceUrl = session.archive_location?.replace('local_archive_har', 'http://127.0.0.1:4444/archives') + '/' + sr
                            if (isPlayableVideo(resourceUrl)) {
                                return <video
                                    key={sr}
                                    src={resourceUrl}
                                    style={{
                                        backgroundColor: '#000',
                                        maxWidth: 300,
                                        maxHeight: 300
                                    }}
                                    controls
                                />
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
                                            title={<Skeleton
                                                animation="wave"
                                                height={10}
                                                width="80%"
                                                style={{marginBottom: 6}}
                                            />}
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
                                                <Stack
                                                    direction={"row"} gap={1} alignItems={"center"}
                                                    justifyContent={"center"}
                                                >
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
                                </Card>
                            }
                        })
                    }
                </Stack>
                <Box sx={{height: 400, width: "100%", overflowY: 'auto'}}>
                    <DataGrid
                        rows={rows}
                        columns={columns}
                        hideFooterPagination
                        hideFooter
                    />
                </Box>
            </Stack>
        );
    }
}
