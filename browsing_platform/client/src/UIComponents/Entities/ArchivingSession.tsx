import React from 'react';
import {IArchiveSession} from "../../types/entities";
import {
    Box, Divider, Fade, IconButton, Stack,
} from "@mui/material";
import {DataGrid} from "@mui/x-data-grid";
import LinkIcon from "@mui/icons-material/Link";
import SelfContainedPopover from "../SelfContainedComponents/selfContainedPopover";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import ReactJson from "react-json-view";

interface IProps {
    session: IArchiveSession,
    mediaStyle?: React.CSSProperties
}

interface IState {
    expandDetails: boolean
}


export default class ArchiveSessionMetadata extends React.Component <IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            expandDetails: false
        };
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
            >
                <Stack
                    direction={"row"}
                    alignItems={"center"}
                    sx={{height: 400, width: "100%", overflow: 'auto'}}
                >
                    {
                        session.attachments?.screen_recordings?.map((sr) => {
                            return <video
                                key={sr}
                                src={session.archive_location + '/' + sr}
                                style={{
                                    backgroundColor: '#000',
                                    maxWidth: '100%',
                                    maxHeight: '100%',
                                }}
                                controls
                            />
                        })
                    }
                </Stack>
                <Box sx={{height: 400, width: 600, overflow: 'auto'}}>
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
