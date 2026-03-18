import React from 'react';
import {Box, Card, CardMedia, Divider, Stack, Typography} from '@mui/material';
import {SearchResult} from '../../services/DataFetcher';
import {anchor_local_static_files} from '../../services/server';

interface Props {
    results: SearchResult[];
}

export default function DefaultSearchResults({results}: Props) {
    if (results.length === 0) {
        return <Box>No results found.</Box>;
    }
    return (
        <Stack spacing={2} divider={<Divider orientation="horizontal" flexItem/>}>
            {results.map((result, idx) => (
                <a key={idx} href={`/${result.page}/${result.id}`} style={{textDecoration: 'none'}}>
                    <Card variant="elevation" elevation={0}>
                        <Typography variant="h6">{result.title}</Typography>
                        {result.details && (
                            <Typography variant="body2">{result.details}</Typography>
                        )}
                        <CardMedia>
                            <Stack direction="row" gap={1}>
                                {result.thumbnails?.map((tn, i) => (
                                    <img
                                        key={i}
                                        src={anchor_local_static_files(tn) || undefined}
                                        alt={`Thumbnail ${i + 1}`}
                                        style={{maxWidth: '100px', maxHeight: '100px'}}
                                    />
                                ))}
                            </Stack>
                        </CardMedia>
                    </Card>
                </a>
            ))}
        </Stack>
    );
}
