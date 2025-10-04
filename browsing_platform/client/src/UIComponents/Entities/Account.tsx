import React from 'react';
import {AccountAndAssociatedEntities} from "../../types/entities";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Box,
    Collapse,
    Grid,
    IconButton,
    Paper,
    Typography
} from "@mui/material";
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import Post from "./Post";
import ReactJson from "react-json-view";

interface IProps {
    account: AccountAndAssociatedEntities
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
        return <Paper>
            <a href={account.url}>
                <Typography variant={"body1"}>{account.url}</Typography>
            </a>
            {account.display_name ? <Typography variant="h5">{account.display_name}</Typography> : null}
            <Typography variant="caption">{account.bio}</Typography>
            <IconButton
                size="small"
                color={"primary"}
                onClick={() => this.setState((curr) => ({...curr, expandDetails: !curr.expandDetails}))}
            >
                <MoreHorizIcon/>
            </IconButton>
            <Collapse in={this.state.expandDetails}>
                    <ReactJson
                        src={account.data}
                        enableClipboard={false}
                    />
            </Collapse>
            <Box>
                <Grid container spacing={2}>
                    {
                        account.account_posts.map((p, p_i) =>{
                            return <React.Fragment key={p_i}>
                                <Post post={p} />
                            </React.Fragment>
                        })
                    }
                </Grid>
            </Box>
        </Paper>
    }
}
