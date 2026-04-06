import React from 'react';
import {Box, Card, Divider, Stack, Typography} from '@mui/material';
import {SearchResultsProps} from './types';
import {SearchResultTags, SearchResultThumbnails, SelectableResultBox} from './SearchResultParts';

export default function AccountSearchResults({results, tagsMap, selectedIds, onToggleSelected}: SearchResultsProps) {
    if (results.length === 0) {
        return <Box>No results found.</Box>;
    }
    return (
        <Stack spacing={2} divider={<Divider orientation="horizontal" flexItem/>}>
            {results.map((result, idx) => {
                const tags = tagsMap?.[result.id] ?? [];
                return (
                    <SelectableResultBox key={idx} id={result.id} page={result.page} selectedIds={selectedIds} onToggleSelected={onToggleSelected}>
                        <Card variant="elevation" elevation={0}>
                            <Typography variant="h6">{result.title}</Typography>
                            {result.details && (
                                <Typography variant="body2">{result.details}</Typography>
                            )}
                            <SearchResultThumbnails thumbnails={result.thumbnails} totalCount={result.metadata?.media_count}/>
                            <SearchResultTags tags={tags}/>
                        </Card>
                    </SelectableResultBox>
                );
            })}
        </Stack>
    );
}
