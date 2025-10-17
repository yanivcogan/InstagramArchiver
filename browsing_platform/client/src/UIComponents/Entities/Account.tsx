import React from 'react';
import {IAccountAndAssociatedEntities} from "../../types/entities";
import {
    Box,
    Button,
    Collapse,
    Grid,
    IconButton,
    Paper,
    Stack,
    Typography
} from "@mui/material";
import LinkIcon from '@mui/icons-material/Link';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import Post from "./Post";
import ReactJson from "react-json-view";

interface IProps {
    account: IAccountAndAssociatedEntities
    mediaStyle?: React.CSSProperties
}

interface IState {
    expandDetails: boolean
    postsToShow: number
}


export default class Account extends React.Component <IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            expandDetails: false,
            postsToShow: 5
        };
    }

    render() {
        const account = this.props.account;
        return <Paper sx={{padding: '1em'}}>
            <Stack gap={0.5} sx={{height: "100%"}}>
                <Stack gap={1} direction={"row"} alignItems={"center"}>
                    <a href={account.url}>
                        <Typography variant={"body1"}>{account.url}</Typography>
                    </a>
                    <IconButton
                        color={"primary"}
                        href={"/account/" + account.id}
                    >
                        <LinkIcon/>
                    </IconButton>
                </Stack>
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
                <Stack direction={"column"} sx={{width: "100%", flexGrow: 1}} gap={1}>
                    {
                        account.account_posts
                            .slice(0, this.state.postsToShow)
                            .map((p, p_i) => {
                                return <React.Fragment key={p_i}>
                                    <Post post={p} mediaStyle={this.props.mediaStyle}/>
                                </React.Fragment>
                            })
                    }
                    <Button
                        variant="contained"
                        disabled={account.account_posts.length <= this.state.postsToShow}
                        onClick={() => this.setState((curr) => ({
                            ...curr,
                            postsToShow: (curr.postsToShow) + 5
                        }))}
                        onDoubleClick={()=> this.setState({postsToShow: account.account_posts.length}) }
                    >
                        Load More Posts
                    </Button>
                </Stack>
            </Stack>
        </Paper>
    }
}
