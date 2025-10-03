import React, {Component, ReactElement} from 'react';
import {Menu} from '@mui/material';
import {SxProps, Theme} from "@mui/system";

interface IProps {
    trigger: (popupVisibilitySetter: (e: React.MouseEvent<HTMLElement>, visibility: boolean) => any) => ReactElement;
    content: ReactElement[];
    popoverSx?: SxProps<Theme> | undefined
}


interface IState {
    visible: boolean;
    anchorEl: HTMLElement | null;
}

export default class SelfContainedMenu extends Component<IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            visible: false,
            anchorEl: null
        };
    }

    render() {
        return (
            <React.Fragment>
                {this.props.trigger((e, visible) => {
                    this.setState({visible, anchorEl: e.currentTarget})
                })}
                <Menu
                    open={this.state.visible}
                    onClose={() => {
                        this.setState({visible: false})
                    }}
                    anchorEl={this.state.anchorEl}
                >
                    {
                        this.props.content
                    }
                </Menu>
            </React.Fragment>
        );
    }
}

