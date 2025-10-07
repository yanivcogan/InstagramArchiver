import React from 'react';
import './lib/variables.scss'
import './lib/global.scss'
import './lib/layout.scss'
import './lib/buttons.scss'
import './lib/classes.scss'

import {BrowserRouter as Router, Route, Routes} from "react-router-dom";
import PubSub from 'pubsub-js';
import events from './lib/events';
import NoMatch from "./pages/404";
import Login from "./pages/Login";


import {KeyStatesProvider} from './services/keys/keyStates';
import {incorporateArrayInQueue, IPopupAlert, IPreparedPopupAlert} from "./services/alerts/alerts";
import withReactErrorSuppression from "./services/reactErrorSuppression/reactErrorSuppression";
import Alert from "./UIComponents/Alert/Alert";
import Account from "./UIComponents/Entities/Account";
import AccountPage from "./pages/AccountPage";
import PostPage from "./pages/PostPage";

interface IAppProps {
}

interface IAppState {
    alertQueue: IPreparedPopupAlert[]
}

class App extends React.Component <IAppProps, IAppState> {
    constructor(props: IAppProps) {
        super(props);
        this.state = {
            alertQueue: []
        };
        PubSub.subscribe(events.alert, (_: string, alert: IPopupAlert) => {
            this.alert(alert)
        });
        PubSub.subscribe(events.clearAlert, (_: string, alertId: number) => {
            this.clearAlert(alertId)
        });
    }

    componentWillUnmount() {
        PubSub.clearAllSubscriptions();
    }

    alert = (alert: IPopupAlert) => {
        let alertQueue = this.state.alertQueue.slice();
        alertQueue = incorporateArrayInQueue(alertQueue, alert);
        this.setState({alertQueue});
    };

    clearAlert = (alertId: number) => {
        let alertQueue = this.state.alertQueue.slice();
        alertQueue = alertQueue.filter((alert) => {
            return alert.id !== alertId;
        })
        this.setState({alertQueue});
    };


    render() {
        return (
            <KeyStatesProvider>
                <Router>
                    <meta/>
                    <Routes>
                        <Route path="/" element={<Login/>}/>
                        <Route path="/login" element={<Login/>}/>
                        <Route path="/account/:id" element={<AccountPage/>}/>
                        <Route path="/post/:id" element={<PostPage/>}/>
                        <Route path="/*" element={<NoMatch/>}/>
                    </Routes>
                    <Alert
                        setQueue={(alertQueue: any) => this.setState({alertQueue})}
                        queue={this.state.alertQueue}
                    />
                </Router>
            </KeyStatesProvider>
        );
    }
}

export default withReactErrorSuppression(App)