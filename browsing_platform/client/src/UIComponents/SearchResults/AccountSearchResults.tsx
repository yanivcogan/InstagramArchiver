import React from 'react';
import {Card, Typography} from '@mui/material';
import {SearchResultsProps} from './types';
import {SearchResultList, SearchResultTags, SearchResultThumbnails, SelectableResultBox} from './SearchResultParts';

export default function AccountSearchResults({results, tagsMap, selectedIds, onToggleSelected, onPrimaryClick}: SearchResultsProps) {
    return (
        <SearchResultList results={results}>
            {(result, idx) => {
                const displayName = result.metadata?.display_name || result.metadata?.url_suffix;
                const primaryLabel = displayName || result.title;
                const tags = tagsMap?.[result.id] ?? [];
                return (
                    <SelectableResultBox key={idx} id={result.id} page={result.page} result={result}
                                        selectedIds={selectedIds} onToggleSelected={onToggleSelected}
                                        onPrimaryClick={onPrimaryClick}>
                        <Card variant="elevation" elevation={0}>
                            <Typography variant="h6">{primaryLabel}</Typography>
                            {displayName && (
                                <Typography variant="body2" color="text.secondary" sx={{mb: 0.5}}>
                                    {result.title}
                                </Typography>
                            )}
                            {result.details && (
                                <Typography variant="body2">{result.details}</Typography>
                            )}
                            <SearchResultThumbnails thumbnails={result.thumbnails} totalCount={result.metadata?.media_count}/>
                            <SearchResultTags tags={tags}/>
                        </Card>
                    </SelectableResultBox>
                );
            }}
        </SearchResultList>
    );
}
