import React from 'react';
import {PostAndAssociatedEntities} from "../../types/entities";
import {Accordion, AccordionDetails, Box, Collapse, Grid, IconButton, Paper, Stack, Typography} from "@mui/material";
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import Media from "./Media";
import ReactJson from "react-json-view";

interface IProps {
    post: PostAndAssociatedEntities
    mediaStyle?: React.CSSProperties
}

interface IState {
    expandDetails: boolean
}


export default class Post extends React.Component <IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            expandDetails: false
        };
    }

    render() {
        const post = this.props.post;
        return <Paper sx={{padding: '1em', boxSizing: 'border-box', width: '100%'}}>
            <Stack gap={0.5}>
                <a href={post.url}>
                    <Typography variant={"body1"}>{post.url}</Typography>
                </a>
                <Typography variant="caption">{post.publication_date}</Typography>
                {post.caption ? <Typography variant="body2">{post.caption}</Typography> : null}
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
                        src={post.data}
                        enableClipboard={false}
                    />
                </Collapse>
                <Box>
                    <Grid container spacing={2}>
                        {
                            post.post_media.map((m, m_i) => {
                                return <Grid item xs={2} key={m_i}>
                                    <Media media={m} mediaStyle={this.props.mediaStyle}/>
                                </Grid>
                            })
                        }
                    </Grid>
                </Box>
            </Stack>
        </Paper>
    }
}
