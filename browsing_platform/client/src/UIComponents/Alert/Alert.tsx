import React, {useState} from 'react';
import "./Alert.scss";
import {IPreparedPopupAlert} from "../../services/alerts/alerts";
import {Button, Card, CardActions, CardContent, CircularProgress, Fade, Modal, Typography} from "@mui/material";
import PubSub from "pubsub-js";
import events from "../../lib/events";

interface IProps {
    queue: IPreparedPopupAlert[],
}

export default function Alert({queue}: IProps) {
    const [awaitingActionCompletion, setAwaitingActionCompletion] = useState(false);

    const close = (alertId?: number) => {
        if (alertId !== undefined) {
            PubSub.publish(events.clearAlert, alertId);
        }
    };

    const alert = queue.length ? queue[0] : null;
    const alertBody = alert ? (alert.html ? alert.html : <Card>
        <CardContent>
            <Typography gutterBottom variant="h5" component="div">
                {alert.title || `Alert`}
            </Typography>
            {alert.message ? (typeof alert.message === "string" ?
                <Typography variant="body2" sx={{color: 'text.secondary'}}>
                    {alert.message}
                </Typography> : alert.message) : null
            }
        </CardContent>
        <CardActions>
            {alert.actions ? alert.actions.map((a, i) => (
                <Button
                    key={i}
                    variant={"contained"}
                    color={"primary"}
                    startIcon={awaitingActionCompletion ? <CircularProgress size={20} color={"info"}/> : null}
                    disabled={awaitingActionCompletion}
                    onClick={async () => {
                        setAwaitingActionCompletion(true);
                        const resOrPromise = a.onClick();
                        const res = resOrPromise instanceof Promise ? await resOrPromise : resOrPromise;
                        if (a.onResolve) {
                            a.onResolve(res, () => close(alert.id));
                        } else {
                            close(alert.id);
                        }
                        if (alert.onClose) alert.onClose();
                        setAwaitingActionCompletion(false);
                    }}
                    {...a.buttonPropsOverride}
                >
                    {a.label}
                </Button>
            )) : null}
        </CardActions>
    </Card>) : null;

    return <Modal
        open={!!queue.length}
        sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backdropFilter: alert?.opaque ? "blur(5px)" : undefined,
            width: "100%",
            '& > .MuiPaper-root': {
                outline: 'none',
                maxHeight: "90%",
                maxWidth: "90%",
                overflowY: "auto",
                ...(alert?.paperRootProps || {})
            }
        }}
        onClose={() => {
            if (alert?.dismissible) {
                if (alert.onClose) alert.onClose();
                close(alert.id);
            }
        }}
    >
        <Fade in={!!queue.length}>
            {alertBody || <div/>}
        </Fade>
    </Modal>
}
