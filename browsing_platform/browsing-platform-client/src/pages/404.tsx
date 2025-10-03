import React from 'react'
import TopNavBar from '../UIComponents/TopNavBar/TopNavBar';
import "./404/404.scss"
import withRouter, {IRouterProps} from "../services/withRouter";

interface IMissingPageProps extends IRouterProps {}

class MissingPage extends React.Component<IMissingPageProps, {}> {
    componentDidMount() {}

    render() {
        return (
            <div className={"page-wrap-event-categories-management"}>
                <TopNavBar>Page not Found</TopNavBar>
                <div className={"not-found-message"}>
                    <div style={{fontWeight: "bold"}}>404</div>
                </div>
            </div>
        )
    }
}

export default withRouter(MissingPage)