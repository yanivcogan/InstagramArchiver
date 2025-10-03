import React, {Component, CSSProperties, ReactElement} from 'react';
import {IconButton, Modal} from '@mui/material';
import {Close as CloseIcon} from '@mui/icons-material';
import './selfContainedModal.scss';

interface IProps {
    trigger: (popupVisibilitySetter: (visibility: boolean) => any) => ReactElement;
    content: (popupVisibilitySetter: (visibility: boolean) => any) => ReactElement;
    noXButton?: boolean
    wrapStyles?: CSSProperties
}


interface IState {
    visible: boolean;
}

export default class SelfContainedModal extends Component<IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            visible: false
        };
    }

    render() {
        return (
            <>
                {this.props.trigger((visible: boolean) => {
                    this.setState({visible})
                })}
                <Modal
                    open={this.state.visible}
                    onClose={() => {
                        this.setState({visible: false})
                    }}
                    className={"modal-center"}
                >
                    <div className="modal-content" style={this.props.wrapStyles}>
                        {
                            this.props.noXButton ? null :
                                <IconButton
                                    onClick={() => {
                                        this.setState({visible: false})
                                    }}
                                >
                                    <CloseIcon/>
                                </IconButton>
                        }
                        {
                            this.props.content(
                                (visibility: boolean) => {
                                    this.setState({visible: visibility});
                                }
                            )
                        }
                    </div>
                </Modal>
            </>
        );
    }
}

