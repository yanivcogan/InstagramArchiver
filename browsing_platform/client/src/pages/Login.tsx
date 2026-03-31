import React, {useEffect, useState} from 'react';
import server from '../services/server';
import cookie from 'js-cookie';
import './login/Login.scss';
import {CircularProgress, FormControl, IconButton, Input, InputLabel, Modal, Stack, Tooltip} from "@mui/material";
import {createTheme, ThemeProvider} from '@mui/material/styles';
import {LocalFlorist, Visibility, VisibilityOff} from "@mui/icons-material";
import {useNavigate, useSearchParams} from "react-router";

const darkTheme = createTheme({
    palette: {
        mode: 'dark',
    },
});

export default function Login() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();

    const [email, setEmail] = useState(searchParams.get("email") || "");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [awaitingAuthentication, setAwaitingAuthentication] = useState(false);
    const [authenticationError, setAuthenticationError] = useState<string | null>(null);

    const redirect = searchParams.get("redirect");

    useEffect(() => {
        document.title = `Login | Browsing Platform`;
        const token = cookie.get('token');
        if (token && token.length) {
            server.get("permissions/", {ignoreErrors: true}).then((res) => {
                if (res?.valid) {
                    proceedToSite();
                }
            }).catch(() => {});
        }
    }, []);

    const proceedToSite = () => {
        if (redirect) {
            try {
                const decoded = decodeURIComponent(redirect);
                if (decoded.startsWith('/') && !decoded.startsWith('//')) {
                    navigate(decoded);
                    return;
                }
            } catch (e) {
                console.log(e);
            }
        }
        navigate("/search/");
    };

    const verifyPasswordLogin = async () => {
        if (awaitingAuthentication) return;
        setAwaitingAuthentication(true);
        try {
            const res = await server.post("login/", {email, password}, undefined, {ignoreErrors: true});
            if (res?.token) {
                cookie.set('token', res.token, {
                    expires: 30,
                    sameSite: 'strict',
                    secure: window.location.protocol === 'https:',
                });
                proceedToSite();
            } else {
                setAuthenticationError(res?.error || 'An Unknown Error Has Occurred');
            }
        } catch (e: any) {
            setAuthenticationError(e?.message || 'An Unknown Error Has Occurred');
        } finally {
            setAwaitingAuthentication(false);
        }
    };

    return <React.Fragment>
        <div className='page-wrap-login'>
            <ThemeProvider theme={darkTheme}>
                <Stack dir="column" alignItems="center" gap={2}>
                    {
                        (window.innerWidth <= 768)
                            ?
                            <Stack className={"welcome-title-wrap"} direction="column" justifyContent="center">
                                <h1 className={"welcome-title"}>Welcome to the Magrefa</h1>
                                <Stack className={"welcome-title-wrap"} direction="row" justifyContent="center">
                                    <h1 className={"title-adornments"}>°𓏲🌿. 🍁⋆˚࿔</h1>
                                    <h1 className={"title-adornments"}>༄˖°.🍂.ೃ࿔*</h1>
                                </Stack>
                            </Stack>
                            : <Stack className={"welcome-title-wrap"} justifyContent="center" direction="row" gap={2}>
                                <h1 className={"title-adornments"}>°𓏲⋆🌿🍁⋆˚࿔</h1>
                                <h1 className={"welcome-title"}>Welcome</h1>
                                <h1 className={"title-adornments"}>༄˖°.🍂.ೃ࿔*</h1>
                            </Stack>
                    }
                    <Stack dir="column" alignItems="center" gap={2} sx={{width: "100%"}}>
                        <h2>{`Login`}</h2>
                        <FormControl
                            variant="outlined"
                            sx={{width: (window.innerWidth <= 768) ? "80%" : "500px"}}
                        >
                            <InputLabel>{`Email Address`}</InputLabel>
                            <Input
                                value={email}
                                dir="ltr"
                                onChange={(e) => setEmail(e.target.value)}
                            />
                        </FormControl>
                    </Stack>
                    <FormControl
                        variant="outlined"
                        sx={{width: (window.innerWidth <= 768) ? "80%" : "500px"}}
                    >
                        <InputLabel>{`Password`}</InputLabel>
                        <Input
                            type={showPassword ? "text" : "password"}
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && password.length) {
                                    verifyPasswordLogin();
                                }
                            }}
                            endAdornment={
                                <Stack direction="row" alignItems="center" gap={0.5}>
                                    <IconButton
                                        size="small"
                                        onClick={() => setShowPassword(prev => !prev)}
                                        aria-label={`Toggle password visibility`}
                                    >
                                        {showPassword ? <VisibilityOff/> : <Visibility/>}
                                    </IconButton>
                                    {
                                        awaitingAuthentication
                                            ? <CircularProgress size={20}/>
                                            : <Tooltip title={`Login`} placement="top" arrow disableInteractive>
                                                <IconButton
                                                    color="success"
                                                    size="small"
                                                    disabled={!password.length}
                                                    onClick={verifyPasswordLogin}
                                                >
                                                    <LocalFlorist/>
                                                </IconButton>
                                            </Tooltip>
                                    }
                                </Stack>
                            }
                        />
                    </FormControl>
                </Stack>
            </ThemeProvider>
        </div>
        <Modal
            open={!!authenticationError}
            onClose={() => setAuthenticationError(null)}
            className={"modal-center"}
        >
            <div className={"authentication-modal"}>
                <h2>Authentication Error</h2>
                <p>{authenticationError}</p>
            </div>
        </Modal>
    </React.Fragment>
}
