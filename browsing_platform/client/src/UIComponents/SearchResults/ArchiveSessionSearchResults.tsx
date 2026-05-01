import React from 'react';
import {Box, Card, Divider, Stack, Typography} from '@mui/material';
import dayjs from 'dayjs';
import {SearchResult} from '../../services/DataFetcher';
import {SearchResultThumbnails} from './SearchResultParts';

interface Props {
    results: SearchResult[];
}

export default function ArchiveSessionSearchResults({results}: Props) {
    if (results.length === 0) {
        return <Box>No results found.</Box>;
    }
    return (
        <Stack spacing={2} divider={<Divider orientation="horizontal" flexItem/>}
               sx={{'@media (max-width: 768px)': {px: '1em'}}}>
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
                            <SearchResultThumbnails thumbnails={result.thumbnails} totalCount={result.metadata?.media_count}/>
                        </Card>
                    </a>
                );
            })}
        </Stack>
    );
}
