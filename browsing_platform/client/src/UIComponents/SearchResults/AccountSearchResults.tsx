import React from 'react';
import {Box, Card, CardMedia, Checkbox, Chip, Divider, Stack, Typography} from '@mui/material';
import {SearchResult} from '../../services/DataFetcher';
import {anchor_local_static_files} from '../../services/server';
import {SearchResultsProps} from './index';

export default function AccountSearchResults({results, tagsMap, selectedIds, onToggleSelected}: SearchResultsProps) {
    if (results.length === 0) {
        return <Box>No results found.</Box>;
    }
    return (
        <Stack spacing={2} divider={<Divider orientation="horizontal" flexItem/>}>
            {results.map((result, idx) => {
                const shown = result.thumbnails?.length ?? 0;
                const total = result.metadata?.media_count ?? 0;
                const tags = tagsMap?.[result.id] ?? [];

                return (
                    <Box
                        key={idx}
                        sx={{position: 'relative', cursor: onToggleSelected ? 'pointer' : undefined}}
                        onClick={onToggleSelected ? (e) => { e.preventDefault(); onToggleSelected(result.id); } : undefined}
                    >
                        {onToggleSelected && (
                            <Checkbox
                                checked={selectedIds?.has(result.id) ?? false}
                                onClick={e => { e.preventDefault(); e.stopPropagation(); onToggleSelected(result.id); }}
                                sx={{position: 'absolute', top: 0, right: 0, zIndex: 1}}
                                size="small"
                            />
                        )}
                        <a href={`/${result.page}/${result.id}`} style={{textDecoration: 'none'}}>
                            <Card variant="elevation" elevation={0}>
                                <Typography variant="h6">{result.title}</Typography>
                                {result.details && (
                                    <Typography variant="body2">{result.details}</Typography>
                                )}
                                <CardMedia>
                                    <Stack direction="row" gap={1} sx={{mt: 1}} alignItems="center" flexWrap="wrap">
                                        {result.thumbnails?.map((tn, i) => (
                                            <img
                                                key={i}
                                                src={anchor_local_static_files(tn) || undefined}
                                                alt={`Thumbnail ${i + 1}`}
                                                style={{maxWidth: '100px', maxHeight: '100px'}}
                                            />
                                        ))}
                                        {total > shown && (
                                            <Typography variant="body2" color="text.secondary">
                                                +{total - shown} more
                                            </Typography>
                                        )}
                                    </Stack>
                                </CardMedia>
                                {tags.length > 0 && (
                                    <Stack direction="row" gap={0.5} flexWrap="wrap" sx={{mt: 0.5}}>
                                        {tags.map(t => (
                                            <Chip key={t.id} label={t.name} size="small" variant="outlined"
                                                  sx={{fontSize: '0.7rem', height: 20}}/>
                                        ))}
                                    </Stack>
                                )}
                            </Card>
                        </a>
                    </Box>
                );
            })}
        </Stack>
    );
}
