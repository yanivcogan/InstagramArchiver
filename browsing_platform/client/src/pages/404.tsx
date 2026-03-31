import React, {useEffect} from 'react'
import TopNavBar from '../UIComponents/TopNavBar/TopNavBar';
import "./404/404.scss"

export default function MissingPage() {
    useEffect(() => {
        document.title = 'Not Found | Browsing Platform';
    }, []);

    return (
        <div className={"page-wrap-event-categories-management"}>
            <TopNavBar>Page not Found</TopNavBar>
            <div className={"not-found-message"}>
                <div style={{fontWeight: "bold"}}>404</div>
            </div>
        </div>
    )
}
