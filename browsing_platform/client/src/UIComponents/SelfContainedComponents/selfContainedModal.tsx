import React, {CSSProperties, ReactElement, useState} from 'react';
import {IconButton, Modal} from '@mui/material';
import {Close as CloseIcon} from '@mui/icons-material';
import './selfContainedModal.scss';

interface IProps {
    trigger: (popupVisibilitySetter: (visibility: boolean) => any) => ReactElement<any>;
    content: (popupVisibilitySetter: (visibility: boolean) => any) => ReactElement<any>;
    noXButton?: boolean
    wrapStyles?: CSSProperties
}

export default function SelfContainedModal({trigger, content, noXButton, wrapStyles}: IProps) {
    const [visible, setVisible] = useState(false);

    return (
        <>
            {trigger(setVisible)}
            <Modal
                open={visible}
                onClose={() => setVisible(false)}
                className={"modal-center"}
            >
                <div className="modal-content" style={wrapStyles}>
                    {!noXButton && (
                        <IconButton onClick={() => setVisible(false)}>
                            <CloseIcon/>
                        </IconButton>
                    )}
                    {content(setVisible)}
                </div>
            </Modal>
        </>
    );
}
