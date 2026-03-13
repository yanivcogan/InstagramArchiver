import React, {ReactElement, useState} from 'react';
import {Menu} from '@mui/material';
import {SxProps, Theme} from "@mui/system";

interface IProps {
    trigger: (popupVisibilitySetter: (e: React.MouseEvent<HTMLElement>, visibility: boolean) => any) => ReactElement<any>;
    content: ReactElement<any>[];
    popoverSx?: SxProps<Theme> | undefined
}

export default function SelfContainedMenu({trigger, content}: IProps) {
    const [visible, setVisible] = useState(false);
    const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

    return (
        <React.Fragment>
            {trigger((e, visibility) => {
                setVisible(visibility);
                setAnchorEl(e.currentTarget);
            })}
            <Menu
                open={visible}
                onClose={() => setVisible(false)}
                anchorEl={anchorEl}
            >
                {content}
            </Menu>
        </React.Fragment>
    );
}
