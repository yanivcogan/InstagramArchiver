import React from 'react';
import {IPostAndAssociatedEntities} from "../../types/entities";
import {Box, Button, CircularProgress, Collapse, Grid, IconButton, Paper, Stack, Typography} from "@mui/material";
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import Media from "./Media";
import ReactJson from "react-json-view";
import LinkIcon from "@mui/icons-material/Link";
import {fetchPostData} from "../../services/DataFetcher";
import {EntityViewerConfig} from "./EntitiesViewerConfig";
import TextField from "@mui/material/TextField";
import TagSelector from "../Tags/TagSelector";
import SaveIcon from "@mui/icons-material/Save";
import {savePostAnnotations} from "../../services/DataSaver";

interface IProps {
    post: IPostAndAssociatedEntities
    viewerConfig?: EntityViewerConfig
}

interface IState {
    post: IPostAndAssociatedEntities
    expandDetails: boolean
    awaitingDetailsFetch: boolean
    savingAnnotations: boolean
}


export default class Post extends React.Component <IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            post: props.post,
            expandDetails: false,
            awaitingDetailsFetch: false,
            savingAnnotations: false
        };
    }

    private fetchPostDetails = async () => {
        const post = this.state.post;
        const itemId = post.id;
        if (this.state.awaitingDetailsFetch || itemId === undefined || itemId === null) {
            return;
        }
        this.setState((curr => ({...curr, awaitingDetailsFetch: true})), async () => {
            post.data = await fetchPostData(itemId);
            this.setState((curr => ({...curr, awaitingDetailsFetch: false, post})));
        });
    }

    render() {
        const post = this.state.post;
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
                            return <Media media={m} viewerConfig={this.props.viewerConfig} key={m_i}/>
                        })
                    }
                </Stack>
                {
                    this.props.viewerConfig?.post?.annotator === "show" ? <Stack gap={1}>
                        <TextField
                            label={"Notes"}
                            multiline
                            value={this.state.post.notes || ""}
                            onChange={(e) => {
                                const post = this.state.post;
                                post.notes = e.target.value;
                                this.setState((curr) => ({...curr, post}))
                            }}
                        />
                        <TagSelector
                            selectedTags={[]}
                            onChange={(tags) => {
                                const post = this.state.post;
                                post.tags = tags;
                                this.setState((curr) => ({...curr, post}))
                            }}
                        />
                        <Button
                            variant="contained"
                            startIcon={this.state.savingAnnotations ? <CircularProgress size={20} color={"inherit"}/> : <SaveIcon/>}
                            onClick={async () => {
                                this.setState((curr) => ({...curr, savingAnnotations: true}) , async () => {
                                    const post = this.state.post;
                                    await savePostAnnotations(post);
                                    this.setState((curr) => ({...curr, savingAnnotations: false}))
                                });
                            }}
                            color={"success"}
                        >
                            Save Annotations
                        </Button>
                    </Stack> : <Stack gap={1}>
                        {
                            post?.tags?.length ? (<React.Fragment>
                                <Typography variant={"subtitle2"}>Tags:</Typography>
                                <Stack direction={"row"} gap={1} flexWrap={"wrap"}>
                                    {
                                        post?.tags?.map((t, t_i) => {
                                            return <Typography variant={"body2"} key={t_i}>{t.name}</Typography>
                                        })
                                    }
                                </Stack>
                            </React.Fragment>) :
                                null
                        }
                        {
                            post?.notes?.length ? (<React.Fragment>
                                <Typography variant={"subtitle2"}>Notes:</Typography>
                                <Typography variant={"body2"}>{post.notes}</Typography>
                            </React.Fragment>) :
                                null
                        }
                    </Stack>
                }
            </Stack>
        </Paper>
    }
}
