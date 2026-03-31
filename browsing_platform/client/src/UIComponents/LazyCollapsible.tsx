import React, {useEffect, useRef, useState} from 'react';
import {Button, CircularProgress, Collapse, Stack} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';

interface IProps {
    label: string;
    onLoad?: () => Promise<void>;
    loading?: boolean;
    defaultExpanded?: boolean;
    children: React.ReactNode;
}

export default function LazyCollapsible({label, onLoad, loading = false, defaultExpanded = false, children}: IProps) {
    const [expanded, setExpanded] = useState(defaultExpanded);
    const calledRef = useRef(false);

    useEffect(() => {
        if (defaultExpanded && onLoad && !calledRef.current) {
            calledRef.current = true;
            onLoad();
        }
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const toggle = async () => {
        const next = !expanded;
        setExpanded(next);
        if (next && onLoad && !calledRef.current) {
            calledRef.current = true;
            await onLoad();
        }
    };

    return (
        <Stack gap={0.5}>
            <Button
                size="small"
                variant="outlined"
                onClick={toggle}
                endIcon={loading ? <CircularProgress size={14}/> : expanded ? <ExpandLessIcon/> : <ExpandMoreIcon/>}
                disabled={loading}
                sx={{justifyContent: "space-between"}}
            >
                {label}
            </Button>
            <Collapse in={expanded}>
                {children}
            </Collapse>
        </Stack>
    );
}
