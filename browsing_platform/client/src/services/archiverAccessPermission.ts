import {useEffect, useState} from 'react';
import cookie from 'js-cookie';
import server from './server';

// Shared "may this user see archiver-access data" check (admin OR archiver).
//
// Module-level cache: many components (a page full of Account cards, the
// community-detection lists) should trigger a single permissions request, not
// one per instance. Keyed on the auth-token cookie so it invalidates
// automatically on logout/login (the token changes) instead of serving a prior
// user's permissions for the SPA session's lifetime.
let cachedToken: string | undefined;
let permissionPromise: Promise<boolean> | null = null;

export const resolveCanViewArchiverAccess = (): Promise<boolean> => {
    const token = cookie.get('token');
    if (permissionPromise === null || token !== cachedToken) {
        cachedToken = token;
        permissionPromise = server.get('permissions/', {ignoreErrors: true})
            .then((res: any) => Boolean(res?.admin || res?.archiver))
            .catch(() => false);
    }
    return permissionPromise;
};

// Convenience hook mirroring the above for components that render conditionally.
export const useCanViewArchiverAccess = (): boolean => {
    const [canView, setCanView] = useState(false);
    useEffect(() => {
        let alive = true;
        resolveCanViewArchiverAccess().then(v => {
            if (alive) setCanView(v);
        });
        return () => {
            alive = false;
        };
    }, []);
    return canView;
};
