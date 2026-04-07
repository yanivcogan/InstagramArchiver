import React from 'react';
import {Card, Typography} from '@mui/material';
import dayjs from 'dayjs';
import {SearchResultsProps} from './types';
import {SearchResultList, SearchResultTags, SearchResultThumbnails, SelectableResultBox} from './SearchResultParts';

export default function PostSearchResults({results, tagsMap, selectedIds, onToggleSelected}: SearchResultsProps) {
    return (
        <SearchResultList results={results}>
            {(result, idx) => {
                const pubDate = result.metadata?.publication_date
                    ? dayjs(result.metadata.publication_date).format('YYYY-MM-DD HH:mm')
                    : null;
                const accountName = result.metadata?.account_display_name
                    || (result.metadata?.account_url
                        ? result.metadata.account_url.replace(/\/$/, '').split('/').pop()
                        : null);
                const primaryLabel = [accountName, pubDate].filter(Boolean).join(' · ');
                const tags = tagsMap?.[result.id] ?? [];

                return (
                    <SelectableResultBox key={idx} id={result.id} page={result.page} selectedIds={selectedIds} onToggleSelected={onToggleSelected}>
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
                            <SearchResultThumbnails thumbnails={result.thumbnails}/>
                            <SearchResultTags tags={tags}/>
                        </Card>
                    </SelectableResultBox>
                );
            }}
        </SearchResultList>
    );
}
