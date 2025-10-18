import React from 'react';
import {IAccountAndAssociatedEntities, IExtractedEntitiesNested, IPostAndAssociatedEntities} from "../../types/entities";
import {Stack} from "@mui/material";
import Post from "./Post";
import Account from "./Account";
import Media from "./Media";

interface IProps {
    entities: IExtractedEntitiesNested
    mediaStyle?: React.CSSProperties
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
                        (account: IAccountAndAssociatedEntities, index: number) => <Account account={account} key={index} mediaStyle={this.props.mediaStyle}/>
                    )
            }
            {
                this.props.entities.posts
                    .sort((a, b) => (new Date(b.publication_date || 0).getTime()) - (new Date(a.publication_date || 0).getTime()))
                    .map(
                        (post: IPostAndAssociatedEntities, index: number) => <Post post={post} key={index} mediaStyle={this.props.mediaStyle}/>
                    )
            }
            {
                this.props.entities.media
                    .map(
                        (media, index: number) => <Media media={media} key={index} mediaStyle={this.props.mediaStyle}/>
                    )
            }
        </Stack>
    }
}
