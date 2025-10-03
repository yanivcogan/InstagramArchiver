import React, {useEffect} from 'react';


const withReactErrorSuppression = <P extends object>(WrappedComponent: React.ComponentType<P>) => {
    return (props: P) => {
        useEffect(() => {
            function hideError(e: ErrorEvent) {
                if (e.message === 'ResizeObserver loop completed with undelivered notifications.') {
                    const resizeObserverErrDiv = document.getElementById(
                        'webpack-dev-server-client-overlay-div'
                    );
                    const resizeObserverErr = document.getElementById(
                        'webpack-dev-server-client-overlay'
                    );
                    if (resizeObserverErr) {
                        resizeObserverErr.setAttribute('style', 'display: none');
                    }
                    if (resizeObserverErrDiv) {
                        resizeObserverErrDiv.setAttribute('style', 'display: none');
                    }
                }
            }

            window.addEventListener('error', hideError);
            return () => {
                window.removeEventListener('error', hideError);
            };
        }, []);

        return <WrappedComponent {...props} />;
    };
}

export default withReactErrorSuppression