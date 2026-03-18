import React from 'react';
import {Box, Card, CardMedia, Divider, Stack, Typography} from '@mui/material';
import dayjs from 'dayjs';
import {SearchResult} from '../../services/DataFetcher';
import {anchor_local_static_files} from '../../services/server';

interface Props {
    results: SearchResult[];
}

export default function PostSearchResults({results}: Props) {
    if (results.length === 0) {
        return <Box>No results found.</Box>;
    }
    return (
        <Stack spacing={2} divider={<Divider orientation="horizontal" flexItem/>}>
            {results.map((result, idx) => {
                const pubDate = result.metadata?.publication_date
                    ? dayjs(result.metadata.publication_date).format('YYYY-MM-DD HH:mm')
                    : null;
                const accountName = result.metadata?.account_display_name
                    || (result.metadata?.account_url
                        ? result.metadata.account_url.replace(/\/$/, '').split('/').pop()
                        : null);
                const primaryLabel = [accountName, pubDate].filter(Boolean).join(' · ');

                return (
                    <a key={idx} href={`/${result.page}/${result.id}`} style={{textDecoration: 'none'}}>
                        <Card variant="elevation" elevation={0}>
                            {primaryLabel && (
                                <Typography variant="h6">{primaryLabel}</Typography>
                            )}
                            {result.title && (
                                <Typography variant="body2" color="text.secondary" sx={{mb: 0.5}}>
                                    {result.title}
                                </Typography>
                            )}
                            {result.details && (
                                <Typography variant="body2">{result.details}</Typography>
                            )}
                            <CardMedia>
                                <Stack direction="row" gap={1} sx={{mt: 1}}>
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
                );
            })}
        </Stack>
    );
}
