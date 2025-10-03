import React, {ReactNode} from 'react';
import server from '../../services/server';
import cookie from 'js-cookie';
import withRouter, {IRouterProps} from "../../services/withRouter";
import {
    AppBar, Toolbar, Drawer,
    List, ListItemButton,
    Stack, Divider,
    IconButton
} from "@mui/material";
import LocalFloristIcon from '@mui/icons-material/LocalFlorist';
import MenuIcon from '@mui/icons-material/Menu';

type IProps = {
    children: ReactNode
} & IRouterProps

interface IState {
    emoji: string,
    menuOpened: boolean,
    permissions: any
}

interface IMenuItem {
    page: string;
    label: string;
    search?: { [key: string]: any };
    endAdornment?: ReactNode;
}

class TopNavBar extends React.Component<IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            menuOpened: false,
            emoji: "🌹",
            permissions: {}
        };
    }

    componentDidMount() {
        this.setState((curr) => ({...curr, permissions: this.getPermissions()}))
    }

    getPermissions() {
        const json = cookie.get("permissions");
        if (!json)
            return {};
        try {
            return JSON.parse(json);
        } catch (e) {
            return {}
        }
    }

    logout() {
        server.get('login/logout/', {})
            .then(() => {
                const cookies = cookie.get();
                Object.keys(cookies).forEach((cookieName) => {
                    cookie.remove(cookieName);
                })
                this.props.navigate('/Login')
            });
    }

    toggleMenu = () => {
        if (!this.state.menuOpened) {
            const possibleMenuEmojis = ["🌹"];
            const emoji = possibleMenuEmojis[Math.floor(Math.random() * possibleMenuEmojis.length)];
            this.setState((curr) => ({...curr, menuOpened: true, emoji: emoji}));
        } else {
            this.setState((curr) => ({...curr, menuOpened: false}));
        }
    }

    goToPage = (page: string, search?: { [key: string]: any }) => {
        this.props.navigate({
            pathname: "/" + page,
            search: search ? Object.keys(search).map(k => "" + k + "=" + search[k]).join("&") : ""
        });
        this.toggleMenu();
    }

    render() {
        return <>
            <AppBar position="static" sx={{backgroundColor: "#282c34"}}>
                <Toolbar>
                    <Stack direction={"row"} gap={2} alignItems={"center"}>
                        <IconButton onClick={this.toggleMenu} color="inherit">
                            <MenuIcon/>
                        </IconButton>
                        {this.props.children}
                    </Stack>
                </Toolbar>
            </AppBar>
                <Drawer open={this.state.menuOpened} onClose={this.toggleMenu}
                        anchor={"left"}>
                        <Stack direction={"column"} sx={{height: "100vh"}}>
                            <AppBar position="static" sx={{backgroundColor: "#282c34"}}>
                                <Toolbar>
                                    <Stack direction={"row"} justifyContent={"center"} sx={{width: "100%"}}>
                                        <LocalFloristIcon/>
                                    </Stack>
                                </Toolbar>
                            </AppBar>
                            <List
                                sx={{
                                    paddingTop: 0,
                                    paddingBottom: 0,
                                    height: "100%",
                                    overflow: "auto",
                                }}
                            >
                                <Divider/>
                                <ListItemButton
                                    onClick={(_) => {
                                        this.logout()
                                    }}
                                >
                                    Logout
                                </ListItemButton>
                            </List>
                        </Stack>
                </Drawer>
        </>
    }
}

export default withRouter(TopNavBar)
