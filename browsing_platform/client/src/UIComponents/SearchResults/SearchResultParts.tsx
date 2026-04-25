import React from 'react';
import {Box, CardMedia, Checkbox, Chip, Divider, Stack, Typography} from '@mui/material';
import {SearchResult} from '../../services/DataFetcher';
import {anchor_local_static_files} from '../../services/server';
import {ITagWithType} from '../../types/tags';

interface SearchResultListProps {
    results: SearchResult[];
    children: (result: SearchResult, idx: number) => React.ReactNode;
}

export function SearchResultList({results, children}: SearchResultListProps) {
    if (results.length === 0) return <Box>No results found.</Box>;
    return (
        <Stack spacing={2} divider={<Divider orientation="horizontal" flexItem/>}>
            {results.map((result, idx) => children(result, idx))}
        </Stack>
    );
}

interface SelectableResultBoxProps {
    id: number;
    page: string;
    result?: SearchResult;
    selectedIds?: Set<number>;
    onToggleSelected?: (id: number) => void;
    onPrimaryClick?: (result: SearchResult) => void;
    children: React.ReactNode;
}

export function SelectableResultBox({id, page, result, selectedIds, onToggleSelected, onPrimaryClick, children}: SelectableResultBoxProps) {
    const interactive = onToggleSelected || onPrimaryClick;
    return (
        <Box
            sx={{position: 'relative', cursor: interactive ? 'pointer' : undefined}}
            onClick={interactive ? (e) => {
                e.preventDefault();
                if (onToggleSelected) onToggleSelected(id);
                else if (onPrimaryClick && result) onPrimaryClick(result);
            } : undefined}
        >
            {onToggleSelected && (
                <Checkbox
                    checked={selectedIds?.has(id) ?? false}
                    onClick={e => { e.preventDefault(); e.stopPropagation(); onToggleSelected(id); }}
                    sx={{position: 'absolute', top: 0, right: 0, zIndex: 1}}
                    size="small"
                />
            )}
            <a href={`/${page}/${id}`} style={{textDecoration: 'none'}}
               onClick={onPrimaryClick ? e => e.preventDefault() : undefined}>
                {children}
            </a>
        </Box>
    );
}

interface SearchResultThumbnailsProps {
    thumbnails?: string[];
    totalCount?: number;
}

export function SearchResultThumbnails({thumbnails, totalCount}: SearchResultThumbnailsProps) {
    const shown = thumbnails?.length ?? 0;
    const total = totalCount ?? shown;
    return (
        <CardMedia>
            <Stack direction="row" gap={1} sx={{mt: 1}} alignItems="center" flexWrap="wrap">
                {thumbnails?.map((tn, i) => (
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
    );
}

interface SearchResultTagsProps {
    tags: ITagWithType[];
}

export function SearchResultTags({tags}: SearchResultTagsProps) {
    if (tags.length === 0) return null;
    return (
        <Stack direction="row" gap={0.5} flexWrap="wrap" sx={{mt: 0.5}}>
            {tags.map(t => (
                <Chip key={t.id} label={t.name} size="small" variant="outlined"
                      sx={{fontSize: '0.7rem', height: 20}}/>
            ))}
        </Stack>
    );
}
