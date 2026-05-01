import React, {useEffect, useState} from 'react';
import {Box, CircularProgress} from '@mui/material';
import {
    checkShareLinkPasswordStatus,
    clearSharePasswordToken,
    getSharePasswordToken,
    getShareTokenFromHref,
    isPasswordTokenExpired,
} from '../../services/linkSharing';
import SharePasswordPrompt from './SharePasswordPrompt';

interface IProps {
    children: React.ReactNode;
}

type GateState = 'checking' | 'open' | 'locked';

export default function SharePasswordGate({children}: IProps) {
    const linkSuffix = getShareTokenFromHref();
    const [state, setState] = useState<GateState>(linkSuffix ? 'checking' : 'open');

    useEffect(() => {
        if (!linkSuffix) {
            setState('open');
            return;
        }
        checkShareLinkPasswordStatus(linkSuffix).then(protected_ => {
            if (protected_ === false) {
                // Confirmed: no password required
                setState('open');
                return;
            }
            if (protected_ === null) {
                // Request failed — could be misconfiguration; don't silently open
                setState('locked');
                return;
            }
            // protected_ === true
            const storedToken = getSharePasswordToken(linkSuffix);
            if (storedToken && !isPasswordTokenExpired(storedToken)) {
                setState('open');
            } else {
                if (storedToken) clearSharePasswordToken(linkSuffix);
                setState('locked');
            }
        });
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [linkSuffix]);

    if (state === 'checking') {
        return (
            <Box sx={{minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
                <CircularProgress/>
            </Box>
        );
    }

    if (state === 'locked' && linkSuffix) {
        return (
            <SharePasswordPrompt
                linkSuffix={linkSuffix}
                onUnlocked={() => setState('open')}
            />
        );
    }

    return <>{children}</>;
}
