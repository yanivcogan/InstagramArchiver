import React, {ReactNode, useState} from 'react';
import server from '../../services/server';
import cookie from 'js-cookie';
import {useNavigate} from "react-router";
import {
    AppBar,
    Divider,
    Drawer,
    IconButton,
    List,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Stack,
    Toolbar
} from "@mui/material";
import LocalFloristIcon from '@mui/icons-material/LocalFlorist';
import MenuIcon from '@mui/icons-material/Menu';
import SearchIcon from "@mui/icons-material/Search";
import UploadIcon from "@mui/icons-material/Upload";
import StorageIcon from "@mui/icons-material/Storage";
import LogoutIcon from '@mui/icons-material/Logout';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';

interface IProps {
    children: ReactNode;
    hideMenuButton?: boolean;
}

export default function TopNavBar({children, hideMenuButton}: IProps) {
    const navigate = useNavigate();
    const [menuOpened, setMenuOpened] = useState(false);

    const logout = () => {
        server.post('login/logout', {}).then(() => {
            const cookies = cookie.get();
            Object.keys(cookies).forEach(name => cookie.remove(name));
            navigate('/Login');
        });
    };

    const toggleMenu = () => setMenuOpened(prev => !prev);

    const goToPage = (page: string, search?: { [key: string]: any }) => {
        navigate({
            pathname: "/" + page,
            search: search ? Object.keys(search).map(k => `${k}=${search[k]}`).join("&") : ""
        });
        toggleMenu();
    };

    return <>
        <AppBar position="static" sx={{backgroundColor: "#282c34"}}>
            <Toolbar>
                <Stack direction={"row"} gap={2} alignItems={"center"} sx={{width: "100%"}}>
                    {!hideMenuButton && (
                        <IconButton onClick={toggleMenu} color="inherit">
                            <MenuIcon/>
                        </IconButton>
                    )}
                    {children}
                </Stack>
            </Toolbar>
        </AppBar>
        <Drawer open={menuOpened} onClose={toggleMenu} anchor={"left"}>
            <Stack direction={"column"} sx={{height: "100vh"}}>
                <AppBar position="static" sx={{backgroundColor: "#282c34"}}>
                    <Toolbar>
                        <Stack direction={"row"} justifyContent={"center"} sx={{width: "100%"}}>
                            <LocalFloristIcon/>
                        </Stack>
                    </Toolbar>
                </AppBar>
                <List sx={{paddingTop: 0, paddingBottom: 0, height: "100%", width: 250, overflow: "auto"}}>
                    <Divider/>
                    <ListItemButton onClick={() => goToPage("search")} href={"/search"}>
                        <ListItemIcon><SearchIcon/></ListItemIcon>
                        <ListItemText primary="Search"/>
                    </ListItemButton>
                    <ListItemButton onClick={() => goToPage("tags")} href={"/tags"}>
                        <ListItemIcon><LocalOfferIcon/></ListItemIcon>
                        <ListItemText primary="Tags"/>
                    </ListItemButton>
                    <ListItemButton onClick={() => goToPage("upload")} href={"/upload"}>
                        <ListItemIcon><UploadIcon/></ListItemIcon>
                        <ListItemText primary="Upload Archives"/>
                    </ListItemButton>
                    <ListItemButton onClick={() => goToPage("incorporate")} href={"/incorporate"}>
                        <ListItemIcon><StorageIcon/></ListItemIcon>
                        <ListItemText primary="Incorporate"/>
                    </ListItemButton>
                    <ListItemButton onClick={logout}>
                        <ListItemIcon><LogoutIcon/></ListItemIcon>
                        <ListItemText primary="Logout"/>
                    </ListItemButton>
                </List>
            </Stack>
        </Drawer>
    </>
}
