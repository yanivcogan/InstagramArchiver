import React from 'react';
import {Box, CardMedia, Checkbox, Chip, Stack, Typography} from '@mui/material';
import {anchor_local_static_files} from '../../services/server';
import {ITagWithType} from '../../types/tags';

interface SelectableResultBoxProps {
    id: number;
    page: string;
    selectedIds?: Set<number>;
    onToggleSelected?: (id: number) => void;
    children: React.ReactNode;
}

export function SelectableResultBox({id, page, selectedIds, onToggleSelected, children}: SelectableResultBoxProps) {
    return (
        <Box
            sx={{position: 'relative', cursor: onToggleSelected ? 'pointer' : undefined}}
            onClick={onToggleSelected ? (e) => { e.preventDefault(); onToggleSelected(id); } : undefined}
        >
            {onToggleSelected && (
                <Checkbox
                    checked={selectedIds?.has(id) ?? false}
                    onClick={e => { e.preventDefault(); e.stopPropagation(); onToggleSelected(id); }}
                    sx={{position: 'absolute', top: 0, right: 0, zIndex: 1}}
                    size="small"
                />
            )}
            <a href={`/${page}/${id}`} style={{textDecoration: 'none'}}>
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
