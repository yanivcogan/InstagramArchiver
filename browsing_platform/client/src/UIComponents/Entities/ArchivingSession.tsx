import React from 'react';
import {IArchiveSession} from "../../types/entities";
import {
    Box,
} from "@mui/material";
import {DataGrid} from "@mui/x-data-grid";

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
            <Box sx={{height: 400, width: 600}}>
                <DataGrid
                    rows={rows}
                    columns={columns}
                    hideFooterPagination
                    hideFooter
                />
            </Box>
        );
    }
}
