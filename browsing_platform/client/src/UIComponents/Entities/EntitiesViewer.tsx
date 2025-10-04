import React from 'react';
import {AccountAndAssociatedEntities, ExtractedEntitiesNested, PostAndAssociatedEntities} from "../../types/entities";
import {Accordion, AccordionDetails, Box, Grid, IconButton, Paper, Stack, Typography} from "@mui/material";
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import Post from "./Post";
import Account from "./Account";
import Media from "./Media";

interface IProps {
    entities: ExtractedEntitiesNested
}

interface IState {}


export default class EntitiesViewer extends React.Component <IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {};
    }

    render() {
        return <Stack gap={1}>
            {
                this.props.entities.accounts
                    .map(
                        (account: AccountAndAssociatedEntities, index: number) => <Account account={account} key={index}/>
                    )
            }
            {
                this.props.entities.posts
                    .map(
                        (post: PostAndAssociatedEntities, index: number) => <Post post={post} key={index}/>
                    )
            }
            {
                this.props.entities.media
                    .map(
                        (media, index: number) => <Media media={media} key={index}/>
                    )
            }
        </Stack>
    }
}
