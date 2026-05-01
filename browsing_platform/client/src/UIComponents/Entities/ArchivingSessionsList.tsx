import React from 'react';
import {Box, CircularProgress, Stack, Typography} from "@mui/material";
import {IArchiveSession} from "../../types/entities";
import ArchivingSession from "./ArchivingSession";

type IProps = {
    sessions: IArchiveSession[] | null;
    loadingSessions: boolean;
};

export default function ArchivingSessionsList({sessions, loadingSessions}: IProps) {
    return <Stack direction={"column"} gap={1} sx={{width: '100%', boxSizing: 'border-box', '@media (max-width: 768px)': {padding: '1em'}}}>
        <Typography variant={"h6"} fontWeight={"bold"}>Archiving History</Typography>
        {
            loadingSessions ?
                <Box sx={{
                    display: "flex", justifyContent: "center", alignItems: "center", height: "30vh",
                    maxWidth: "100%", overflowX: "auto"
                }}>
                    <CircularProgress/>
                </Box> :
                (!sessions || sessions.length === 0) ? <div>No archiving sessions</div> :
                    <Stack direction={"row"} gap={1} sx={{"overflowX": "auto", width: '100%'}}>
                        {sessions.map((s, s_i) => (
                            <Box key={s_i}>
                                <ArchivingSession archiveSession={s}/>
                            </Box>
                        ))}
                    </Stack>
        }
    </Stack>
}
