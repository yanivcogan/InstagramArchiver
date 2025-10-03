import React, {Component, CSSProperties, ReactElement} from 'react';
import {Backdrop, Fab, Grow, IconButton, Stack} from '@mui/material';
import {Close as CloseIcon} from '@mui/icons-material';
import OpenWithIcon from '@mui/icons-material/OpenWith';
import './selfContainedModal.scss';
import {Rnd} from "react-rnd";
import {TransparentTooltip} from "../StyledComponents/TransparentTooltip";

interface IProps {
    trigger: (popupVisibilitySetter: (visibility: boolean) => any, visibility: boolean) => ReactElement | null;
    content: (popupVisibilitySetter: (visibility: boolean) => any, visibility: boolean) => ReactElement | null;
    noXButton?: boolean
    wrapStyles?: CSSProperties
}


interface IState {
    visible: boolean;
    showBackdrop: boolean;
    animationActive: boolean;
    showCloseTooltip: boolean;
}

export default class SelfContainedRnDModal extends Component<IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            visible: false,
            showBackdrop: false,
            animationActive: false,
            showCloseTooltip: false
        };
    }

    render() {
        return (
            <div>
                {this.props.trigger((visible: boolean) => {
                    this.setState({
                        visible, showBackdrop: true,
                        animationActive: true
                    })
                }, this.state.visible)}
                <div>
                    <Backdrop
                        open={this.state.visible && this.state.showBackdrop}
                        onClick={() => {
                            this.setState({showBackdrop: false})
                        }}
                        className={"modal-center"}
                    />
                    {(this.state.visible || this.state.animationActive) && <div className={"rnd-modal-wrap"}><Rnd
                        default={{
                            width: "75vw",
                            height: "75vh",
                            x: window.innerWidth / 2 - window.innerWidth * 0.75 / 2,
                            y: window.innerHeight / 2 - window.innerHeight * 0.75 / 2,
                        }}
                        dragHandleClassName={"rnd-drag-handle"}
                        onDragStart={() => {
                            this.setState({showBackdrop: false, showCloseTooltip: false});
                        }}
                        onResizeStart={() => {
                            this.setState({showBackdrop: false, showCloseTooltip: false});
                        }}
                    ><Grow in={this.state.visible} addEndListener={() => {
                        this.setState((curr) => ({...curr, animationActive: false}))
                    }
                    }>
                        <div style={{width: "100%", height: "100%", position: "relative"}}>
                            <div style={{position: "absolute", left: "-3em", top: "0"}}>
                                <Stack
                                    direction={"column"}
                                    gap={1}
                                >
                                    <Fab
                                        color="primary" aria-label="move"
                                        size={"small"}
                                        sx={{
                                            pointerEvents: "all",
                                            cursor: "all-scroll",
                                            zIndex: 5000
                                        }}
                                        className={"rnd-drag-handle"}
                                    >
                                        <OpenWithIcon/>
                                    </Fab>
                                    <Fab
                                        color="error" aria-label="close"
                                        size={"small"}
                                        sx={{
                                            pointerEvents: "all",
                                            cursor: "pointer",
                                            zIndex: 5000
                                        }}
                                        onClick={() => {
                                            this.setState({visible: false});
                                        }}
                                    >
                                        <CloseIcon/>
                                    </Fab>
                                </Stack>
                            </div>
                            <div
                                className="rnd-modal-content"
                                onMouseEnter={() => {
                                    this.setState((curr) => ({...curr, showCloseTooltip: true}))
                                }}
                            >
                                {
                                    this.props.noXButton ? null :
                                        <IconButton
                                            onClick={() => {
                                                this.setState({visible: false, animationActive: true})
                                            }}
                                        >
                                            <CloseIcon/>
                                        </IconButton>
                                }
                                {
                                    this.props.content(
                                        (visibility: boolean) => {
                                            this.setState({
                                                visible: visibility,
                                                animationActive: true,
                                                showCloseTooltip: true
                                            });
                                        }, this.state.visible
                                    )
                                }
                            </div>
                        </div>
                    </Grow>
                    </Rnd></div>}
                </div>
            </div>
        );
    }
}

