import React, {useEffect, useState} from 'react';
import 'material-react-toastify/dist/ReactToastify.css';
import './lib/variables.scss'
import './lib/global.scss'
import './lib/layout.scss'

import {BrowserRouter as Router, Route, Routes} from "react-router";
import PubSub from 'pubsub-js';
import events from './lib/events';
import NoMatch from "./pages/404";
import Login from "./pages/Login";

import {LocalizationProvider} from '@mui/x-date-pickers/LocalizationProvider';
import {AdapterDayjs} from '@mui/x-date-pickers/AdapterDayjs';
import {KeyStatesProvider} from './services/keys/keyStates';
import {ToastContainer} from "material-react-toastify";
import {incorporateArrayInQueue, IPopupAlert, IPreparedPopupAlert} from "./services/alerts/alerts";
import AlertQueueModal from "./services/alerts/AlertQueueModal";
import AccountPage from "./pages/AccountPage";
import PostPage from "./pages/PostPage";
import MediaPage from "./pages/MediaPage";
import SessionPage from "./pages/SessionPage";
import SearchPage from "./pages/SearchPage";
import UploadPage from "./pages/Upload";
import IncorporatePage from "./pages/Incorporate";
import TagManagementPage from "./pages/TagManagementPage";

export default function App() {
    const [alertQueue, setAlertQueue] = useState<IPreparedPopupAlert[]>([]);

    useEffect(() => {
        // Clean up stale TUS upload fingerprints that accumulate in localStorage
        Object.keys(localStorage).filter(k => k.startsWith('tus::')).forEach(k => localStorage.removeItem(k));

        function hideError(e: ErrorEvent) {
            if (e.message === 'ResizeObserver loop completed with undelivered notifications.') {
                const resizeObserverErrDiv = document.getElementById('webpack-dev-server-client-overlay-div');
                const resizeObserverErr = document.getElementById('webpack-dev-server-client-overlay');
                if (resizeObserverErr) resizeObserverErr.setAttribute('style', 'display: none');
                if (resizeObserverErrDiv) resizeObserverErrDiv.setAttribute('style', 'display: none');
            }
        }
        window.addEventListener('error', hideError);

        const alertToken = PubSub.subscribe(events.alert, (_: string, alert: IPopupAlert) => {
            setAlertQueue(curr => incorporateArrayInQueue(curr.slice(), alert));
        });
        const clearToken = PubSub.subscribe(events.clearAlert, (_: string, alertId: number) => {
            setAlertQueue(curr => curr.filter(a => a.id !== alertId));
        });

        return () => {
            window.removeEventListener('error', hideError);
            PubSub.unsubscribe(alertToken);
            PubSub.unsubscribe(clearToken);
        };
    }, []);

    return (
        <LocalizationProvider dateAdapter={AdapterDayjs}>
        <KeyStatesProvider>
            <Router>
                <meta/>
                <Routes>
                    <Route path="/" element={<Login/>}/>
                    <Route path="/login" element={<Login/>}/>
                    <Route path="/account/pk/:platformId" element={<AccountPage/>}/>
                    <Route path="/account/url/*" element={<AccountPage/>}/>
                    <Route path="/account/:id" element={<AccountPage/>}/>
                    <Route path="/post/pk/:platformId" element={<PostPage/>}/>
                    <Route path="/post/url/*" element={<PostPage/>}/>
                    <Route path="/post/:id" element={<PostPage/>}/>
                    <Route path="/media/pk/:platformId" element={<MediaPage/>}/>
                    <Route path="/media/:id" element={<MediaPage/>}/>
                    <Route path="/archive/:id" element={<SessionPage/>}/>
                    <Route path="/search" element={<SearchPage/>}/>
                    <Route path="/upload" element={<UploadPage/>}/>
                    <Route path="/incorporate" element={<IncorporatePage/>}/>
                    <Route path="/tags" element={<TagManagementPage/>}/>
                    <Route path="/*" element={<NoMatch/>}/>
                </Routes>
                <ToastContainer
                    position="bottom-left"
                    bodyStyle={{color: '#000'}}
                />
                <AlertQueueModal alertQueue={alertQueue}/>
            </Router>
        </KeyStatesProvider>
        </LocalizationProvider>
    );
}
