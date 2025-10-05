import React from 'react';
import './login/Login.scss';
import withRouter, {IRouterProps} from "../services/withRouter";
import {
    Box,
    CircularProgress,
} from "@mui/material";
import {ExtractedEntitiesNested} from "../types/entities";
import {fetchAccount} from "../UIComponents/Entities/DataFetcher";
import EntitiesViewer from "../UIComponents/Entities/EntitiesViewer";
import TopNavBar from "../UIComponents/TopNavBar/TopNavBar";

type IProps = {} & IRouterProps;

interface IState {
    id: number | null;
    data: ExtractedEntitiesNested | null;
    loadingData: boolean;
}

class AccountPage extends React.Component<IProps, IState> {
    constructor(props: IProps) {
        super(props);
        const idArg = this.props.params.id;
        const id = idArg === undefined ? null : parseInt(idArg);
        this.state = {
            id,
            data: null,
            loadingData: id !== null,
        }
    }

    componentDidUpdate() {
        const id_param = this.props.params.id;
        const id = id_param === undefined ? null : parseInt(id_param);
        if (id !== this.state.id) {
            this.setState((curr) => ({...curr, id}), async () => {
                await this.fetchData()
            })
        }
    }

    async componentDidMount() {
        await this.fetchData()
    }

    fetchData = async () => {
        const id = this.state.id;
        if (id === null) {
            return;
        }
        this.setState((curr) => ({...curr, loadingData: true}), async () => {
            const data = await fetchAccount(
                id,
                {
                    flattened_entities_transform: {
                        retain_only_media_with_local_files: true,
                        local_files_root: null,
                    },
                    nested_entities_transform: {
                        retain_only_posts_with_media: true,
                        retain_only_accounts_with_posts: false,
                    }
                }
            )
            this.setState((curr) => ({...curr, data, loadingData: false}))
        });
    }

    renderData() {
        const data = this.state.data;
        const loadingData = this.state.loadingData;
        if (loadingData) {
            return <Box sx={{display: "flex", justifyContent: "center", alignItems: "center", height: "100%"}}>
                <CircularProgress/>
            </Box>
        }
        if (!data) {
            return <div>No data</div>
        }
        return <EntitiesViewer
            entities={data}
            mediaStyle={{
                maxWidth: '17vw',
                maxHeight: '50vh',
            }}
        />
    }

    render() {
        return <div className={"page-wrap"}>
            <TopNavBar>
                Account Data
            </TopNavBar>
            <div className={"page-content content-wrap"}>
                {this.renderData()}
            </div>
        </div>
    }
}

export default withRouter(AccountPage);