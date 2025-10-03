import {Button, ButtonOwnProps, Card, CardActions, CardContent, Typography} from "@mui/material";
import React from "react";
import {t} from "@lingui/core/macro";
import PubSub from "pubsub-js";
import events from "../../lib/events";

export interface IPopupAlertAction {
    label?: string;
    buttonPropsOverride?: Partial<ButtonOwnProps>;
    onClick: () => any;
    onResolve?: (res: any, closeNotification: () => void) => void;
}

export interface IPopupAlert {
    id?: number;
    title?: string;
    message?: React.ReactElement | string;
    actions?: IPopupAlertAction[];
    html?: React.ReactElement;
    dismissible?: boolean;
    opaque?: boolean;
    onClose?: () => void;
    flush?: boolean;
    paperRootProps?: React.CSSProperties;
}

export interface IPreparedPopupAlert extends IPopupAlert {}

export const incorporateArrayInQueue = (queue: IPreparedPopupAlert[], alert: IPopupAlert): IPreparedPopupAlert[] => {
    const preparedAlert: IPreparedPopupAlert = {
        ...alert,
        id: alert.id || Date.now().valueOf()
    }
    if (alert.flush === true) {
        return [preparedAlert];
    } else {
        return [...queue, preparedAlert];
    }
}