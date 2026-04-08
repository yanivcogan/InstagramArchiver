import React from 'react';
import {Stack, Tooltip, Typography} from "@mui/material";
import {ITagWithType} from "../../types/tags";

interface IProps {
    tags: ITagWithType[];
}

export default function InlineTagsDisplay({tags}: IProps) {
    if (tags.length === 0) return null;
    return <Stack direction="row" gap={0.75} flexWrap="wrap" alignItems="baseline">
        <Typography variant="caption" color="text.secondary" sx={{fontWeight: 600}}>Tags:</Typography>
        {tags.map((tag, index) => (
            <Tooltip key={index} title={tag.tag_type_name} arrow disableInteractive>
                <Typography component="span" variant="caption" sx={{
                    padding: '0.1em 0.4em',
                    backgroundColor: '#e0e0e0',
                    borderRadius: '4px',
                }}>
                    {tag.name}
                    {tag.assignment_notes && (
                        <Typography component="span" variant="caption"
                                    sx={{ml: 0.5, color: 'text.secondary', fontStyle: 'italic'}}>
                            ({tag.assignment_notes})
                        </Typography>
                    )}
                </Typography>
            </Tooltip>
        ))}
    </Stack>;
}
