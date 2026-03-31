import React from 'react';
import PubSub from 'pubsub-js';
import {Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import events from '../../lib/events';
import {IPreparedPopupAlert} from './alerts';

interface Props {
    alertQueue: IPreparedPopupAlert[];
}

export default function AlertQueueModal({alertQueue}: Props) {
    const alert = alertQueue[0];
    if (!alert) return null;

    const close = () => {
        PubSub.publish(events.clearAlert, alert.id);
        alert.onClose?.();
    };

    const handleAction = async (action: NonNullable<IPreparedPopupAlert['actions']>[number]) => {
        const res = await action.onClick();
        if (action.onResolve) {
            action.onResolve(res, close);
        } else {
            close();
        }
    };

    return (
        <Dialog
            open
            onClose={alert.dismissible ? close : undefined}
            slotProps={{backdrop: {style: alert.opaque ? {backgroundColor: 'rgba(0,0,0,0.85)'} : undefined}}}
            PaperProps={{style: alert.paperRootProps}}
        >
            {alert.title && (
                <DialogTitle sx={{pr: 6}}>
                    {alert.title}
                    {alert.dismissible && (
                        <IconButton onClick={close} size="small" sx={{position: 'absolute', right: 8, top: 8}}>
                            <CloseIcon fontSize="small"/>
                        </IconButton>
                    )}
                </DialogTitle>
            )}
            {(alert.message || alert.html) && (
                <DialogContent>
                    {alert.html ?? alert.message}
                </DialogContent>
            )}
            {alert.actions && alert.actions.length > 0 && (
                <DialogActions>
                    {alert.actions.map((action, i) => (
                        <Button
                            key={i}
                            onClick={() => handleAction(action)}
                            {...action.buttonPropsOverride}
                        >
                            {action.label}
                        </Button>
                    ))}
                </DialogActions>
            )}
        </Dialog>
    );
}
