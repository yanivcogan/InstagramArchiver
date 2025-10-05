import React from 'react';
import {AccountAndAssociatedEntities, ExtractedEntitiesNested, PostAndAssociatedEntities} from "../../types/entities";
import {Stack} from "@mui/material";
import Post from "./Post";
import Account from "./Account";
import Media from "./Media";

interface IProps {
    entities: ExtractedEntitiesNested
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
                        (account: AccountAndAssociatedEntities, index: number) => <Account account={account} key={index} mediaStyle={this.props.mediaStyle}/>
                    )
            }
            {
                this.props.entities.posts
                    .map(
                        (post: PostAndAssociatedEntities, index: number) => <Post post={post} key={index} mediaStyle={this.props.mediaStyle}/>
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
