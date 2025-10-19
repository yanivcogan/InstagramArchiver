import React from 'react';
import {IPostAndAssociatedEntities} from "../../types/entities";
import {Box, CircularProgress, Collapse, Grid, IconButton, Paper, Stack, Typography} from "@mui/material";
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import Media from "./Media";
import ReactJson from "react-json-view";
import LinkIcon from "@mui/icons-material/Link";
import {fetchPostData} from "../../services/DataFetcher";

interface IProps {
    post: IPostAndAssociatedEntities
    mediaStyle?: React.CSSProperties
}

interface IState {
    expandDetails: boolean
    awaitingDetailsFetch: boolean
}


export default class Post extends React.Component <IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            expandDetails: false,
            awaitingDetailsFetch: false
        };
    }

    private fetchPostDetails = async () => {
        const itemId = this.props.post.id;
        if (this.state.awaitingDetailsFetch || itemId === undefined || itemId === null) {
            return;
        }
        this.setState((curr => ({...curr, awaitingDetailsFetch: true})), async () => {
            this.props.post.data = await fetchPostData(itemId);
            this.setState((curr => ({...curr, awaitingDetailsFetch: false})));
        });
    }

    render() {
        const post = this.props.post;
        return <Paper sx={{padding: '1em', boxSizing: 'border-box', width: '100%'}}>
            <Stack gap={0.5}>
                <Stack gap={1} direction={"row"} alignItems={"center"}>
                    <a href={post.url}>
                        <Typography variant={"body1"}>{post.url}</Typography>
                    </a>
                    <IconButton
                        color={"primary"}
                        href={"/post/" + post.id}
                    >
                        <LinkIcon/>
                    </IconButton>
                </Stack>
                <Typography variant="caption">{post.publication_date}</Typography>
                {post.caption ? <Typography variant="body2">{post.caption}</Typography> : null}
                <span>
                    <IconButton
                        size="small"
                        color={"primary"}
                        onClick={() => this.setState((curr) => ({
                            ...curr,
                            expandDetails: !curr.expandDetails
                        }), async () => {
                            if (this.state.expandDetails && (post.data === undefined || post.data === null)) {
                                await this.fetchPostDetails();
                            }
                        })}
                    >
                        <MoreHorizIcon/>
                    </IconButton>
                </span>
                <Collapse in={this.state.expandDetails}>
                    {
                        this.state.awaitingDetailsFetch ?
                            <CircularProgress size={20}/> :
                            this.props.post.data ?
                                <ReactJson
                                    src={post.data}
                                    enableClipboard={false}
                                /> :
                                null
                    }
                </Collapse>
                <Stack direction={"row"} useFlexGap={true} gap={1} flexWrap={"wrap"}>
                    {
                        post.post_media.map((m, m_i) => {
                            return <Media media={m} mediaStyle={this.props.mediaStyle} key={m_i}/>
                        })
                    }
                </Stack>
            </Stack>
        </Paper>
    }
}
