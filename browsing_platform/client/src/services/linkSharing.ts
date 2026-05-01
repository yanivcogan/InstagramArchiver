import config from './config';

export const SHARE_URL_PARAM = 'share';

const apiBase = () => config.serverPath + 'api/';

export const getShareTokenFromHref = () => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(SHARE_URL_PARAM);
}

const _pwTokenKey = (linkSuffix: string) => `share_pw_${linkSuffix}`;

export const getSharePasswordToken = (linkSuffix: string): string | null => {
    return localStorage.getItem(_pwTokenKey(linkSuffix));
};

export const setSharePasswordToken = (linkSuffix: string, token: string): void => {
    localStorage.setItem(_pwTokenKey(linkSuffix), token);
};

export const clearSharePasswordToken = (linkSuffix: string): void => {
    localStorage.removeItem(_pwTokenKey(linkSuffix));
};

export const isPasswordTokenExpired = (token: string): boolean => {
    try {
        const padded = token + '='.repeat((4 - token.length % 4) % 4);
        const decoded = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
        // payload format: "{link_suffix}:{expiry_unix_s}:{sig}"
        // link_suffix and sig have no colons (alphanumeric / base64url), so split gives 3 parts
        const parts = decoded.split(':');
        if (parts.length !== 3) return true;
        const expiry = parseInt(parts[1], 10);
        if (isNaN(expiry)) return true;
        return Date.now() / 1000 > expiry;
    } catch {
        return true;
    }
};

export const verifySharePassword = async (linkSuffix: string, password: string): Promise<string | null> => {
    try {
        const res = await fetch(apiBase() + 'share/verify_password/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: JSON.stringify({link_suffix: linkSuffix, password}),
        });
        if (!res.ok) return null;
        const data = await res.json().catch(() => null);
        return data?.token ?? null;
    } catch {
        return null;
    }
};

const _passwordStatusCache = new Map<string, { value: boolean; expiresAt: number }>();
const _PASSWORD_STATUS_TTL_MS = 5 * 60 * 1000;

/** Returns true/false on a clean response, null if the request failed (treat as unknown). */
export const checkShareLinkPasswordStatus = async (linkSuffix: string): Promise<boolean | null> => {
    const cached = _passwordStatusCache.get(linkSuffix);
    if (cached && Date.now() < cached.expiresAt) {
        return cached.value;
    }
    try {
        const res = await fetch(apiBase() + `share/link_info/${linkSuffix}/`, {
            method: 'GET',
            headers: {'Accept': 'application/json'},
        });
        if (!res.ok) return null;
        const data = await res.json().catch(() => null);
        const value: boolean = data?.password_protected ?? false;
        _passwordStatusCache.set(linkSuffix, {value, expiresAt: Date.now() + _PASSWORD_STATUS_TTL_MS});
        return value;
    } catch {
        return null;
    }
};
