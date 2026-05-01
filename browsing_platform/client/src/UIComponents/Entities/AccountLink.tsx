import React from 'react';
import {Link, Typography} from "@mui/material";

/**
 * Extracts the Instagram handle from an account URL.
 * e.g. "https://www.instagram.com/somehandle" → "@somehandle"
 */
function extractHandle(url: string): string {
    const trimmed = url.replace(/\/$/, '');
    const parts = trimmed.split('/');
    const handle = parts[parts.length - 1];
    return handle ? `@${handle}` : url;
}

/**
 * Returns the best short label for an account: display_name, then @handle from URL, then raw URL.
 */
export function accountLabel(url?: string, displayName?: string): string {
    if (displayName) return displayName;
    if (url) return extractHandle(url);
    return '(unknown)';
}

interface IProps {
    url?: string;
    displayName?: string;
    accountId?: number;
}

/**
 * Renders an account identifier as a hyperlink to the internal account page
 * (if accountId is known), or plain text otherwise.
 */
export default function AccountLink({url, displayName, accountId}: IProps) {
    const label = accountLabel(url, displayName);
    if (accountId != null) {
        return (
            <Link href={`/account/${accountId}`} underline="hover" color="inherit">
                <Typography variant="body2" component="span">{label}</Typography>
            </Link>
        );
    }
    return <Typography variant="body2" component="span">{label}</Typography>;
}
