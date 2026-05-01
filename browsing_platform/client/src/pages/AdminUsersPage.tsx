import React, {useEffect, useState} from 'react';
import server, {HTTP_METHODS} from '../services/server';
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControl,
    FormControlLabel,
    IconButton,
    Input,
    InputLabel,
    Stack,
    Switch,
    Tooltip,
    Typography,
} from "@mui/material";
import {DataGrid, GridColDef} from "@mui/x-data-grid";
import {Delete, Edit, Lock, LockOpen, PersonAdd, Visibility, VisibilityOff, VpnKey} from "@mui/icons-material";
import PageShell from "./PageShell";

interface UserRow {
    id: number;
    email: string;
    admin: boolean;
    locked: boolean;
    totp_configured: boolean;
    force_pwd_reset: boolean;
    last_login: string | null;
    login_attempts: number;
}

interface EditUserData {
    email: string;
    admin: boolean;
    locked: boolean;
    force_pwd_reset: boolean;
    temp_password: string;
}

export default function AdminUsersPage() {
    useEffect(() => {
        document.title = "User Management | Browsing Platform";
        loadUsers();
    }, []);

    const [users, setUsers] = useState<UserRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Add user dialog
    const [addOpen, setAddOpen] = useState(false);
    const [addEmail, setAddEmail] = useState("");
    const [addTempPwd, setAddTempPwd] = useState("");
    const [addAdmin, setAddAdmin] = useState(false);
    const [addBusy, setAddBusy] = useState(false);
    const [addError, setAddError] = useState<string | null>(null);
    const [showAddPwd, setShowAddPwd] = useState(false);

    // Edit user dialog
    const [editUser, setEditUser] = useState<UserRow | null>(null);
    const [editData, setEditData] = useState<EditUserData>({email: "", admin: false, locked: false, force_pwd_reset: false, temp_password: ""});
    const [editBusy, setEditBusy] = useState(false);
    const [editError, setEditError] = useState<string | null>(null);
    const [showEditPwd, setShowEditPwd] = useState(false);

    // Delete confirm
    const [deleteUser, setDeleteUser] = useState<UserRow | null>(null);
    const [deleteBusy, setDeleteBusy] = useState(false);

    // Reset 2FA confirm
    const [reset2faUser, setReset2faUser] = useState<UserRow | null>(null);
    const [reset2faBusy, setReset2faBusy] = useState(false);

    const loadUsers = async () => {
        setLoading(true);
        try {
            const res = await server.get("admin/users/");
            setUsers(res || []);
        } catch (e: any) {
            setError(e?.message || "Failed to load users");
        } finally {
            setLoading(false);
        }
    };

    const handleAddUser = async () => {
        setAddBusy(true);
        setAddError(null);
        try {
            await server.post("admin/users/", {email: addEmail, admin: addAdmin, temp_password: addTempPwd});
            setAddOpen(false);
            setAddEmail(""); setAddTempPwd(""); setAddAdmin(false);
            loadUsers();
        } catch (e: any) {
            setAddError(e?.message || "Failed to create user");
        } finally {
            setAddBusy(false);
        }
    };

    const openEdit = (user: UserRow) => {
        setEditUser(user);
        setEditData({email: user.email, admin: user.admin, locked: user.locked, force_pwd_reset: user.force_pwd_reset, temp_password: ""});
        setEditError(null);
    };

    const handleEditUser = async () => {
        if (!editUser) return;
        setEditBusy(true);
        setEditError(null);
        const payload: any = {
            email: editData.email,
            admin: editData.admin,
            locked: editData.locked,
            force_pwd_reset: editData.force_pwd_reset,
        };
        if (editData.temp_password) payload.temp_password = editData.temp_password;
        try {
            await server.post(`admin/users/${editUser.id}`, payload, HTTP_METHODS.patch);
            setEditUser(null);
            loadUsers();
        } catch (e: any) {
            setEditError(e?.message || "Failed to update user");
        } finally {
            setEditBusy(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteUser) return;
        setDeleteBusy(true);
        try {
            await server.post(`admin/users/${deleteUser.id}`, {}, HTTP_METHODS.delete);
            setDeleteUser(null);
            loadUsers();
        } catch (e: any) {
            setError(e?.message || "Failed to delete user");
        } finally {
            setDeleteBusy(false);
        }
    };

    const handleReset2fa = async () => {
        if (!reset2faUser) return;
        setReset2faBusy(true);
        try {
            await server.post(`admin/users/${reset2faUser.id}/reset-2fa`, {});
            setReset2faUser(null);
            loadUsers();
        } catch (e: any) {
            setError(e?.message || "Failed to reset 2FA");
        } finally {
            setReset2faBusy(false);
        }
    };

    const columns: GridColDef[] = [
        {field: "email", headerName: "Email", flex: 2, minWidth: 200},
        {
            field: "admin", headerName: "Role", width: 90,
            renderCell: (p) => p.value ? <Chip label="Admin" color="warning" size="small"/> : <Chip label="User" size="small"/>
        },
        {
            field: "locked", headerName: "Status", width: 100,
            renderCell: (p) => p.value
                ? <Chip label="Locked" color="error" size="small" icon={<Lock fontSize="small"/>}/>
                : <Chip label="Active" color="success" size="small" icon={<LockOpen fontSize="small"/>}/>
        },
        {
            field: "totp_configured", headerName: "2FA", width: 80,
            renderCell: (p) => p.value
                ? <Chip label="On" color="success" size="small"/>
                : <Chip label="Off" color="default" size="small"/>
        },
        {
            field: "force_pwd_reset", headerName: "Force Reset", width: 110,
            renderCell: (p) => p.value ? <Chip label="Yes" color="warning" size="small"/> : null
        },
        {
            field: "last_login", headerName: "Last Login", flex: 1, minWidth: 140,
            renderCell: (p) => p.value ? new Date(p.value).toLocaleString() : "Never"
        },
        {field: "login_attempts", headerName: "Failures", width: 80},
        {
            field: "actions", headerName: "Actions", width: 160, sortable: false,
            renderCell: (p) => (
                <Stack direction="row" gap={0.5} alignItems="center" sx={{height: "100%"}}>
                    <Tooltip title="Edit"><IconButton size="small" onClick={() => openEdit(p.row)}><Edit fontSize="small"/></IconButton></Tooltip>
                    <Tooltip title="Reset 2FA"><IconButton size="small" onClick={() => setReset2faUser(p.row)}><VpnKey fontSize="small"/></IconButton></Tooltip>
                    <Tooltip title="Delete"><IconButton size="small" color="error" onClick={() => setDeleteUser(p.row)}><Delete fontSize="small"/></IconButton></Tooltip>
                </Stack>
            )
        },
    ];

    return (
        <PageShell title="User Management" subtitle={null} headerRight={
            <Button variant="contained" startIcon={<PersonAdd/>} onClick={() => setAddOpen(true)} size="small">
                Add User
            </Button>
        }>
            {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

            <Box sx={{height: 480}}>
                <DataGrid
                    rows={users}
                    columns={columns}
                    loading={loading}
                    disableRowSelectionOnClick
                    density="compact"
                    pageSizeOptions={[25, 50, 100]}
                />
            </Box>

            {/* Add User Dialog */}
            <Dialog open={addOpen} onClose={() => { setAddOpen(false); setAddError(null); }} maxWidth="xs" fullWidth>
                <DialogTitle>Add User</DialogTitle>
                <DialogContent>
                    <Stack gap={2} sx={{mt: 1}}>
                        {addError && <Alert severity="error">{addError}</Alert>}
                        <Typography variant="body2" color="text.secondary">
                            The new user will be required to change their password and set up 2FA on first login.
                        </Typography>
                        <FormControl variant="standard" fullWidth>
                            <InputLabel>Email</InputLabel>
                            <Input value={addEmail} onChange={(e) => setAddEmail(e.target.value)} type="email" autoComplete="off"/>
                        </FormControl>
                        <FormControl variant="standard" fullWidth>
                            <InputLabel>Temporary Password</InputLabel>
                            <Input
                                value={addTempPwd}
                                onChange={(e) => setAddTempPwd(e.target.value)}
                                type={showAddPwd ? "text" : "password"}
                                autoComplete="new-password"
                                endAdornment={
                                    <IconButton size="small" onClick={() => setShowAddPwd(p => !p)}>
                                        {showAddPwd ? <VisibilityOff/> : <Visibility/>}
                                    </IconButton>
                                }
                            />
                        </FormControl>
                        <FormControlLabel
                            control={<Switch checked={addAdmin} onChange={(e) => setAddAdmin(e.target.checked)}/>}
                            label="Admin"
                        />
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => { setAddOpen(false); setAddError(null); }}>Cancel</Button>
                    <Button
                        variant="contained"
                        disabled={!addEmail || !addTempPwd || addBusy}
                        onClick={handleAddUser}
                    >
                        {addBusy ? <CircularProgress size={18}/> : "Create"}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Edit User Dialog */}
            <Dialog open={!!editUser} onClose={() => setEditUser(null)} maxWidth="xs" fullWidth>
                <DialogTitle>Edit User — {editUser?.email}</DialogTitle>
                <DialogContent>
                    <Stack gap={2} sx={{mt: 1}}>
                        {editError && <Alert severity="error">{editError}</Alert>}
                        <FormControl variant="standard" fullWidth>
                            <InputLabel>Email</InputLabel>
                            <Input value={editData.email} onChange={(e) => setEditData(d => ({...d, email: e.target.value}))} type="email" autoComplete="off"/>
                        </FormControl>
                        <FormControl variant="standard" fullWidth>
                            <InputLabel>New Temporary Password (optional)</InputLabel>
                            <Input
                                value={editData.temp_password}
                                onChange={(e) => setEditData(d => ({...d, temp_password: e.target.value}))}
                                type={showEditPwd ? "text" : "password"}
                                autoComplete="new-password"
                                placeholder="Leave blank to keep current"
                                endAdornment={
                                    <IconButton size="small" onClick={() => setShowEditPwd(p => !p)}>
                                        {showEditPwd ? <VisibilityOff/> : <Visibility/>}
                                    </IconButton>
                                }
                            />
                        </FormControl>
                        <FormControlLabel
                            control={<Switch checked={editData.admin} onChange={(e) => setEditData(d => ({...d, admin: e.target.checked}))}/>}
                            label="Admin"
                        />
                        <FormControlLabel
                            control={<Switch checked={editData.locked} onChange={(e) => setEditData(d => ({...d, locked: e.target.checked}))}/>}
                            label="Account Locked"
                        />
                        <FormControlLabel
                            control={<Switch checked={editData.force_pwd_reset} onChange={(e) => setEditData(d => ({...d, force_pwd_reset: e.target.checked}))}/>}
                            label="Force Password Reset on Next Login"
                        />
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setEditUser(null)}>Cancel</Button>
                    <Button variant="contained" disabled={editBusy} onClick={handleEditUser}>
                        {editBusy ? <CircularProgress size={18}/> : "Save"}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Delete Confirm */}
            <Dialog open={!!deleteUser} onClose={() => setDeleteUser(null)} maxWidth="xs">
                <DialogTitle>Delete User</DialogTitle>
                <DialogContent>
                    <Typography>
                        Permanently delete <strong>{deleteUser?.email}</strong>? This cannot be undone.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleteUser(null)}>Cancel</Button>
                    <Button variant="contained" color="error" disabled={deleteBusy} onClick={handleDelete}>
                        {deleteBusy ? <CircularProgress size={18}/> : "Delete"}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Reset 2FA Confirm */}
            <Dialog open={!!reset2faUser} onClose={() => setReset2faUser(null)} maxWidth="xs">
                <DialogTitle>Reset 2FA</DialogTitle>
                <DialogContent>
                    <Typography>
                        Reset 2FA for <strong>{reset2faUser?.email}</strong>? Their sessions will be invalidated
                        and they will be required to set up 2FA again on next login.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setReset2faUser(null)}>Cancel</Button>
                    <Button variant="contained" color="warning" disabled={reset2faBusy} onClick={handleReset2fa}>
                        {reset2faBusy ? <CircularProgress size={18}/> : "Reset 2FA"}
                    </Button>
                </DialogActions>
            </Dialog>
        </PageShell>
    );
}
