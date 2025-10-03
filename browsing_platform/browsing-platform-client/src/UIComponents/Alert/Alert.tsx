import React from 'react';
import "./Alert.scss";
import {IPreparedPopupAlert} from "../../services/alerts/alerts";
import {Button, Card, CardActions, CardContent, CircularProgress, Fade, Modal, Typography} from "@mui/material";
import {t} from "@lingui/core/macro";
import PubSub from "pubsub-js";
import events from "../../lib/events";


interface IProps {
    queue: IPreparedPopupAlert[],
    setQueue: (queue: IPreparedPopupAlert[]) => any
}

interface IState {
    awaitingActionCompletion: boolean;
}


export default class Alert extends React.Component <IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            awaitingActionCompletion: false,
        };
    }

    close = (alertId?: number) => {
        if (alertId !== undefined) {
            PubSub.publish(events.clearAlert, alertId);
        }
    }

    render() {
        const queue = this.props.queue;
        const alert = queue.length ? queue[0] : null;
        const alertBody = alert ? (alert.html ? alert.html : <Card>
            <CardContent>
                <Typography gutterBottom variant="h5" component="div">
                    {alert.title || t`Alert`}
                </Typography>
                {
                    alert.message ? (typeof alert.message === "string" ?
                        <Typography variant="body2" sx={{color: 'text.secondary'}}>
                            {alert.message}
                        </Typography> : alert.message) : null
                }
            </CardContent>
            <CardActions>
                {
                    alert.actions ? alert.actions.map((a, i) => {
                        return <Button
                            key={i}
                            variant={"contained"}
                            color={"primary"}
                            startIcon={
                                this.state.awaitingActionCompletion ?
                                    <CircularProgress size={20} color={"info"}/> : null
                            }
                            disabled={this.state.awaitingActionCompletion}
                            onClick={async () => {
                                this.setState((curr) => ({...curr, awaitingActionCompletion: true}), async () => {
                                    const resOrPromise = a.onClick();
                                    const res = resOrPromise instanceof Promise ? await resOrPromise : resOrPromise;
                                    if (a.onResolve) {
                                        a.onResolve(res, () => {
                                            this.close(alert.id);
                                        })
                                    } else {
                                        this.close(alert.id);
                                    }
                                    if (alert.onClose) {
                                        alert.onClose();
                                    }
                                    this.setState((curr) => ({...curr, awaitingActionCompletion: false}))
                                })
                            }}
                            {...a.buttonPropsOverride}
                        >
                            {a.label}
                        </Button>
                    }) : null
                }
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
                    if (alert.onClose) {
                        alert.onClose();
                    }
                    this.close(alert.id);
                }
            }}
        >
            <Fade in={!!queue.length}>
                {alertBody || <div/>}
            </Fade>
        </Modal>
    }
}
