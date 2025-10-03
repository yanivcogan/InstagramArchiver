import fetch, {Headers} from 'node-fetch';
import config from './config';
import PubSub from "pubsub-js";
import events from "../lib/events";
import cookie from "js-cookie";
import {IPopupAlert} from "./alerts/alerts";

const apiPath = 'api/';

// TODO: move to common server/client code folder
enum serverErrorAlerts {
    missingPermission,
    missingToken
}

export enum HTTP_METHODS {
    post,
    get,
    delete,
    put,
    options,
    head,
    patch,
}

export interface IRequestOptions {
    ignoreErrors?: boolean,
}

export interface IErrorResponse {
    error: string
}

function get(path: string, options?: IRequestOptions) {
    return post(path, {}, HTTP_METHODS.get, options)
}

const post = async (path: string, data: {
    [key: string]: any
}, method?: HTTP_METHODS, options?: IRequestOptions): Promise<any> => {
    const fixedMethod = method === undefined ? HTTP_METHODS.post : method;
    const headers = new Headers();
    headers.set('Accept', 'application/json');
    headers.set('Content-Type', 'application/json');
    const token: string | undefined = cookie.get("token");
    if (token) {
        headers.set("Authorization", "token:" + token)
    }
    const res = await fetch(config.serverPath + apiPath + path, {
        method: HTTP_METHODS[fixedMethod],
        body: (fixedMethod === HTTP_METHODS.get) ? undefined : JSON.stringify(data),
        headers,
    });
    const resAsJson = res.status === 401 ? {error: "missing permissions"} : await res.json();
    return handleResult(resAsJson, fixedMethod, path, data, options);
}

function handleResult(json: any, method: HTTP_METHODS, path: string, data?: {
    [key: string]: any
}, options?: IRequestOptions) {
    const currPosition = encodeURIComponent(window.location.pathname + window.location.search);
    return new Promise((resolve) => {
        let suppressResult = false;
        if (json && json.error && !(options && options.ignoreErrors)) {
            if (json.error === "missing token") {
                suppressResult = true;
                const missingTokenAlert: IPopupAlert = {
                    title: `Invalid Token`,
                    message: `You are not logged in, please log in again`,
                    actions: [
                        {
                            label: `Login`,
                            onClick: async () => {
                                window.location.href = '/Login?redirect=' + currPosition;
                            },
                            onResolve: (_, closeNotification) => {
                                closeNotification()
                            }
                        }
                    ],
                    dismissible: false,
                }
                PubSub.publish(events.alert, missingTokenAlert);
            } else if (json.error === "missing permissions") {
                const missingTokenAlert: IPopupAlert = {
                    title: `Missing Permissions`,
                    message: `Your user doesn't have permissions to do this action, would you like to switch user?`,
                    actions: [
                        {
                            label: `Switch User`,
                            onClick: async () => {
                                window.location.href = '/Login?redirect=' + currPosition;
                            },
                            onResolve: (_, closeNotification) => {
                                closeNotification()
                            }
                        },
                        {
                            label: `Cancel`,
                            onClick: async () => {
                                return
                            },
                            onResolve: (_, closeNotification) => {
                                closeNotification()
                            }
                        },
                    ],
                    dismissible: true,
                }
                suppressResult = true;
                PubSub.publish(events.alert, missingTokenAlert);
            }
        }
        if (!suppressResult) {
            resolve(json);
        }
    });
}

const server = {
    get,
    post
}

export default (server)
