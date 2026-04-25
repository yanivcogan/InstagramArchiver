import React from 'react';
import {Card, Typography} from '@mui/material';
import {SearchResultsProps} from './types';
import {SearchResultList, SearchResultTags, SearchResultThumbnails, SelectableResultBox} from './SearchResultParts';

export default function AccountSearchResults({results, tagsMap, selectedIds, onToggleSelected, onPrimaryClick}: SearchResultsProps) {
    return (
        <SearchResultList results={results}>
            {(result, idx) => {
                const tags = tagsMap?.[result.id] ?? [];
                return (
                    <SelectableResultBox key={idx} id={result.id} page={result.page} result={result}
                                        selectedIds={selectedIds} onToggleSelected={onToggleSelected}
                                        onPrimaryClick={onPrimaryClick}>
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
            }}
        </SearchResultList>
    );
}
