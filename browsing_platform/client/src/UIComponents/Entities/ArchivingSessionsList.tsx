import React from 'react';
import {
    Box,
    CircularProgress, Stack,
} from "@mui/material";
import {IArchiveSession,} from "../../types/entities";
import ArchivingSession from "src/UIComponents/Entities/ArchivingSession";

type IProps = {
    sessions: IArchiveSession[] | null;
    loadingSessions: boolean;
};

interface IState {}

class ArchivingSessionsList extends React.Component<IProps, IState> {
    constructor(props: IProps) {
        super(props);
    }

    render() {
        const sessions = this.props.sessions;
        const loadingSessions = this.props.loadingSessions;
        if (loadingSessions) {
            return <Box sx={{
                display: "flex", justifyContent: "center", alignItems: "center", height: "30vh",
                maxWidth: "100%", overflowX: "auto"
            }}>
                <CircularProgress/>
            </Box>
        }
        if (!sessions || sessions.length === 0) {
            return <div>No archiving sessions</div>
        }
        return <Stack direction={"row"} gap={1} sx={{"overflowX": "auto", width: '100%'}}>
            {
                sessions.map((s, s_i) => {
                    return <Box key={s_i}>
                        <ArchivingSession
                            session={s}
                        />
                    </Box>
                })
            }
        </Stack>
    }
}

export default ArchivingSessionsList;