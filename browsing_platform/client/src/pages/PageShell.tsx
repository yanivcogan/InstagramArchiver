import React from 'react';
import {CircularProgress, Divider, Stack, Typography} from "@mui/material";
import TopNavBar from "../UIComponents/TopNavBar/TopNavBar";

interface PageShellProps {
    hideMenu?: boolean;
    title: string;
    subtitle: React.ReactNode;
    headerRight?: React.ReactNode;
    children: React.ReactNode;
}

export default function PageShell({hideMenu, title, subtitle, headerRight, children}: PageShellProps) {
    return (
        <div className={"page-wrap"}>
            <TopNavBar hideMenuButton={hideMenu}>
                <Stack direction={"row"} alignItems={"center"} justifyContent={"space-between"} gap={1} sx={{width: '100%'}}>
                    <Stack direction={"row"} alignItems={"center"} gap={1}>
                        <Typography>{title}</Typography>
                        {subtitle}
                    </Stack>
                    {headerRight}
                </Stack>
            </TopNavBar>
            <div className={"page-content content-wrap"}>
                <Stack gap={2} sx={{width: '100%'}} divider={<Divider orientation="horizontal" flexItem/>}>
                    {children}
                </Stack>
            </div>
        </div>
    );
}

export function PageSubtitleLoading({data, children}: {data: unknown, children: React.ReactNode}) {
    return data
        ? <>{children}</>
        : <CircularProgress color={"primary"} size={"16"}/>;
}
