import React, {useState} from 'react';
import {Box, Fade, Typography} from '@mui/material';
import dayjs from 'dayjs';
import {SearchResult} from '../../services/DataFetcher';
import {anchor_local_static_files} from '../../services/server';

interface CellProps {
    result: SearchResult;
}

function MediaSearchResultCell({result}: CellProps) {
    const [hovered, setHovered] = useState(false);
    const thumbnail = result.thumbnails?.[0];

    const pubDate = result.metadata?.publication_date
        ? dayjs(result.metadata.publication_date).format('YYYY-MM-DD')
        : null;
    const accountName = result.metadata?.account_display_name
        || (result.metadata?.account_url
            ? result.metadata.account_url.replace(/\/$/, '').split('/').pop()
            : null);

    return (
        <a href={`/${result.page}/${result.id}`} style={{textDecoration: 'none'}}>
            <Box
                sx={{
                    position: 'relative',
                    aspectRatio: '1',
                    backgroundColor: '#111',
                    overflow: 'hidden',
                    cursor: 'pointer',
                }}
                onMouseEnter={() => setHovered(true)}
                onMouseLeave={() => setHovered(false)}
            >
                {thumbnail && (
                    <img
                        src={anchor_local_static_files(thumbnail) || undefined}
                        alt=""
                        style={{width: '100%', height: '100%', objectFit: 'cover', display: 'block'}}
                    />
                )}
                <Fade in={hovered} timeout={300}>
                    <Box
                        sx={{
                            position: 'absolute',
                            bottom: 0,
                            left: 0,
                            width: '100%',
                            boxSizing: 'border-box',
                            backgroundColor: 'rgba(0,0,0,0.7)',
                            color: '#fff',
                            p: 1,
                        }}
                    >
                        {accountName && (
                            <Typography variant="caption" display="block" noWrap>
                                {accountName}
                            </Typography>
                        )}
                        {pubDate && (
                            <Typography variant="caption" display="block" noWrap>
                                {pubDate}
                            </Typography>
                        )}
                    </Box>
                </Fade>
            </Box>
        </a>
    );
}

interface Props {
    results: SearchResult[];
}

export default function MediaSearchResults({results}: Props) {
    if (results.length === 0) {
        return <Box>No results found.</Box>;
    }
    return (
        <Box
            sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
                gap: 1,
            }}
        >
            {results.map((result, idx) => (
                <MediaSearchResultCell key={idx} result={result}/>
            ))}
        </Box>
    );
}
