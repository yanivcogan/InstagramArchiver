import React, {ReactElement, useState} from 'react';
import {Popover, PopoverProps} from '@mui/material';

interface IProps {
    trigger: (popupVisibilitySetter: (e: React.MouseEvent<HTMLElement>, visibility: boolean) => any) => ReactElement<any>;
    content: (popupVisibilitySetter: (visibility: boolean) => any) => ReactElement<any>;
    popoverProps?: Partial<PopoverProps>
}

export default function SelfContainedPopover({trigger, content, popoverProps}: IProps) {
    const [visible, setVisible] = useState(false);
    const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

    return (
        <React.Fragment>
            {trigger((e, visibility) => {
                setVisible(visibility);
                setAnchorEl(e.currentTarget);
            })}
            <Popover
                open={visible}
                onClose={() => setVisible(false)}
                sx={{'& .MuiPaper-root': {padding: '1em'}}}
                anchorEl={anchorEl}
                {...popoverProps}
            >
                {content(setVisible)}
            </Popover>
        </React.Fragment>
    );
}
