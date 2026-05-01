import React from 'react';
import {Box, CircularProgress, Typography} from '@mui/material';

interface DataLoadGuardProps {
    loadingData: boolean;
    fetchError: string | null;
    data: unknown;
    children: React.ReactNode;
}

export default function DataLoadGuard({loadingData, fetchError, data, children}: DataLoadGuardProps) {
    if (loadingData) {
        return (
            <Box sx={{display: "flex", justifyContent: "center", alignItems: "center", height: "100%"}}>
                <CircularProgress/>
            </Box>
        );
    }
    if (fetchError) {
        return <Typography color="text.secondary">{fetchError}</Typography>;
    }
    if (!data) {
        return <div>No data</div>;
    }
    return <>{children}</>;
}
