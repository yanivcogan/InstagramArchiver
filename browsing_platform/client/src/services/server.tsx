import config from './config';
import PubSub from "pubsub-js";
import events from "../lib/events";
import cookie from "js-cookie";
import {IPopupAlert} from "./alerts/alerts";
import {getShareTokenFromHref} from "./linkSharing";

const apiPath = 'api/';

export enum HTTP_METHODS {
    post,
    get,
    delete,
    put,
    options,
    head,
    patch,
}

interface IRequestOptions {
    ignoreErrors?: boolean,
    abortSignal?: AbortSignal,
}

class ServerError extends Error {
    status: number;

    constructor(status: number, message: string) {
        super(message);
        this.status = status;
        this.name = 'ServerError';
    }
}

const get = (path: string, options?: IRequestOptions) => {
    return post(path, {}, HTTP_METHODS.get, options)
}

const post = async (
    path: string,
    data: { [key: string]: any },
    method?: HTTP_METHODS,
    options?: IRequestOptions
): Promise<any> => {
    const fixedMethod = method ?? HTTP_METHODS.post;
    const headers = new Headers();
    headers.set('Accept', 'application/json');
    headers.set('Content-Type', 'application/json');
    const token: string | undefined = cookie.get("token");
    if (token) {
        headers.set("Authorization", "token:" + token);
    }
    const shareLink = getShareTokenFromHref();
    if (shareLink) {
        headers.set("X-Share-Link", shareLink);
    }
    const res = await fetch(config.serverPath + apiPath + path, {
        method: HTTP_METHODS[fixedMethod],
        body: fixedMethod === HTTP_METHODS.get ? undefined : JSON.stringify(data),
        headers,
        signal: options?.abortSignal,
    });

    const resJson = await res.json().catch(() => null);

    if (res.ok) {
        return resJson;
    }

    if (!options?.ignoreErrors) {
        if (res.status === 401) {
            const currPosition = encodeURIComponent(window.location.pathname + window.location.search);
            const missingTokenAlert: IPopupAlert = {
                title: `Missing Permissions`,
                message: `Your user doesn't have permissions to do this action, would you like to switch user?`,
                actions: [
                    {
                        label: `Switch User`,
                        onClick: async () => {
                            window.location.href = '/Login?redirect=' + currPosition;
                        },
                        onResolve: (_, closeNotification) => closeNotification(),
                    },
                    {
                        label: `Cancel`,
                        onClick: async () => {},
                        onResolve: (_, closeNotification) => closeNotification(),
                    },
                ],
                dismissible: true,
            };
            PubSub.publish(events.alert, missingTokenAlert);
        }
    }

    const errorMessage = resJson?.error || resJson?.detail || `Request failed with status ${res.status}`;
    return Promise.reject(new ServerError(res.status, errorMessage));
}

export const anchor_local_static_files = (path?: string) => {
    if (path === undefined || path === null) {
        return null;
    }
    const baseUrl = config.serverPath.replace(/\/$/, '');
    if (path && path.startsWith("local_archive_har")) {
        // todo test on dev with pnpm start ie not a prod build.
        //  path = path.replace("local_archive_har", "http://127.0.0.1:4444/archives");
        path = path.replace("local_archive_har", `${baseUrl}/archives`);
    } else if (path && path.startsWith("local_thumbnails")) {
        //  path = path.replace("local_thumbnails", "http://127.0.0.1:4444/thumbnails");
        path = path.replace("local_thumbnails", `${baseUrl}/thumbnails`);
    }
    return path;
}

const postFormData = async (path: string, formData: FormData): Promise<any> => {
    const headers = new Headers();
    headers.set('Accept', 'application/json');
    const token: string | undefined = cookie.get("token");
    if (token) {
        headers.set("Authorization", "token:" + token);
    }
    const shareLink = getShareTokenFromHref();
    if (shareLink) {
        headers.set("X-Share-Link", shareLink);
    }
    const res = await fetch(config.serverPath + apiPath + path, {
        method: 'POST',
        body: formData,
        headers,
    });
    const resJson = await res.json().catch(() => null);
    if (res.ok) return resJson;
    const errorMessage = resJson?.error || resJson?.detail || `Request failed with status ${res.status}`;
    return Promise.reject(new ServerError(res.status, errorMessage));
};

const server = {
    get,
    post,
    postFormData,
}

export default (server)
