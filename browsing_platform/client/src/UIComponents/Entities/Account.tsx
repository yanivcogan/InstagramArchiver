import React from 'react';
import {AccountAndAssociatedEntities} from "../../types/entities";
import {
    Box,
    Collapse,
    Grid,
    IconButton,
    Paper,
    Stack,
    Typography
} from "@mui/material";
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import Post from "./Post";
import ReactJson from "react-json-view";

interface IProps {
    account: AccountAndAssociatedEntities
    mediaStyle?: React.CSSProperties
}

interface IState {
    expandDetails: boolean
}


export default class Account extends React.Component <IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            expandDetails: false
        };
    }

    render() {
        const account = this.props.account;
        return <Paper sx={{padding: '1em'}}>
            <Stack gap={0.5}>
                <a href={account.url}>
                    <Typography variant={"body1"}>{account.url}</Typography>
                </a>
                {account.display_name ? <Typography variant="h4">{account.display_name}</Typography> : null}
                <Typography variant="caption">{account.bio}</Typography>
                <span>
                    <IconButton
                        size="small"
                        color={"primary"}
                        onClick={() => this.setState((curr) => ({...curr, expandDetails: !curr.expandDetails}))}
                    >
                        <MoreHorizIcon/>
                    </IconButton>
                </span>
                <Collapse in={this.state.expandDetails}>
                    <ReactJson
                        src={account.data}
                        enableClipboard={false}
                    />
                </Collapse>
                <Box>
                    <Grid container spacing={2}>
                        {
                            account.account_posts.map((p, p_i) => {
                                return <React.Fragment key={p_i}>
                                    <Post post={p} mediaStyle={this.props.mediaStyle}/>
                                </React.Fragment>
                            })
                        }
                    </Grid>
                </Box>
            </Stack>
        </Paper>
    }
}
