import React from 'react';
import {Box, Card, CardMedia, Divider, Stack, Typography} from '@mui/material';
import dayjs from 'dayjs';
import {SearchResult} from '../../services/DataFetcher';
import {anchor_local_static_files} from '../../services/server';

interface Props {
    results: SearchResult[];
}

export default function ArchiveSessionSearchResults({results}: Props) {
    if (results.length === 0) {
        return <Box>No results found.</Box>;
    }
    return (
        <Stack spacing={2} divider={<Divider orientation="horizontal" flexItem/>}>
            {results.map((result, idx) => {
                const archiveDate = result.metadata?.archiving_timestamp
                    ? dayjs(result.metadata.archiving_timestamp).format('YYYY-MM-DD HH:mm')
                    : null;

                return (
                    <a key={idx} href={`/${result.page}/${result.id}`} style={{textDecoration: 'none'}}>
                        <Card variant="elevation" elevation={0}>
                            <Typography variant="h6">{result.title}</Typography>
                            {archiveDate && (
                                <Typography variant="body2" color="text.secondary" sx={{mb: 0.5}}>
                                    Archived on: {archiveDate}
                                </Typography>
                            )}
                            {result.details && (
                                <Typography variant="body2">{result.details}</Typography>
                            )}
                            <CardMedia>
                                <Stack direction="row" gap={1} sx={{mt: 1}} alignItems="center">
                                    {result.thumbnails?.map((tn, i) => (
                                        <img
                                            key={i}
                                            src={anchor_local_static_files(tn) || undefined}
                                            alt={`Thumbnail ${i + 1}`}
                                            style={{maxWidth: '100px', maxHeight: '100px'}}
                                        />
                                    ))}
                                    {(() => {
                                        const shown = result.thumbnails?.length ?? 0;
                                        const total = result.metadata?.media_count ?? 0;
                                        return total > shown ? (
                                            <Typography variant="body2" color="text.secondary">
                                                +{total - shown} more
                                            </Typography>
                                        ) : null;
                                    })()}
                                </Stack>
                            </CardMedia>
                        </Card>
                    </a>
                );
            })}
        </Stack>
    );
}
