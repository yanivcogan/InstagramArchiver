import {styled} from "@mui/system";
import {IconButton, IconButtonProps} from "@mui/material";


interface ExpandMoreProps extends IconButtonProps {
    expand: boolean;
}

export const ExpandMore = styled((props: ExpandMoreProps) => {
    const {expand, ...other} = props;
    return <IconButton {...other} />;
})(({theme}) => ({
    marginLeft: 'auto',
    variants: [
        {
            props: ({expand}) => !expand,
            style: {
                transform: 'rotate(0deg)',
            },
        },
        {
            props: ({expand}) => !!expand,
            style: {
                transform: 'rotate(180deg)',
            },
        },
    ],
}));