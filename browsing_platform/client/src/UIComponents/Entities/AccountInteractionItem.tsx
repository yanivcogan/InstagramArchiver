import React from 'react';
import { Box, Link, Stack, Typography } from '@mui/material';
import { SvgIconProps } from '@mui/material';
import dayjs from 'dayjs';

interface IProps {
    Icon: React.ComponentType<SvgIconProps>;
    color: 'primary' | 'error' | 'warning';
    action: string;
    authorId?: number;
    authorLabel?: string;
    postId?: number;
    postDate?: string;
    children?: React.ReactNode;
}

export default function AccountInteractionItem({ Icon, color, action, authorId, authorLabel, postId, postDate, children }: IProps) {
    const formattedDate = postDate ? dayjs.utc(postDate).format('YYYY-MM-DD') : null;

    return (
        <Box
            sx={{
                pl: 1.5,
                borderLeft: '2px solid',
                borderColor: `${color}.light`,
                borderRadius: '0 4px 4px 0',
                py: 0.25,
                transition: 'background-color 0.15s, border-color 0.15s',
                '&:hover': { bgcolor: 'action.hover', borderColor: `${color}.main` },
            }}
        >
            <Stack direction="row" gap={0.75} alignItems="flex-start">
                <Icon sx={{ fontSize: 14, color: 'text.disabled', mt: '2px', flexShrink: 0 }} />
                <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.5 }}>
                    {action}
                    {(authorId || authorLabel) && (
                        <>
                            {' by '}
                            {authorId ? (
                                <Link
                                    href={`/account/${authorId}`}
                                    underline="hover"
                                    sx={{ color: 'text.primary', fontWeight: 600, fontSize: 'inherit' }}
                                >
                                    {authorLabel || 'unknown'}
                                </Link>
                            ) : (
                                <Box component="span" sx={{ fontWeight: 600, color: 'text.primary' }}>
                                    {authorLabel}
                                </Box>
                            )}
                        </>
                    )}
                    {formattedDate && (
                        <>
                            {' · '}
                            {postId ? (
                                <Link
                                    href={`/post/${postId}`}
                                    underline="hover"
                                    sx={{ color: 'text.secondary', fontSize: 'inherit', fontFamily: 'monospace' }}
                                >
                                    {formattedDate}
                                </Link>
                            ) : (
                                <Box component="span" sx={{ fontFamily: 'monospace' }}>{formattedDate}</Box>
                            )}
                        </>
                    )}
                </Typography>
            </Stack>
            {children}
        </Box>
    );
}
