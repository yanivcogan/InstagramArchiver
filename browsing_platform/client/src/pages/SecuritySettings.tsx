import React, {useEffect, useState} from 'react';
import server, {HTTP_METHODS} from '../services/server';
import cookie from 'js-cookie';
import {
    Alert,
    Box,
    Button,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControl,
    IconButton,
    Input,
    InputLabel,
    LinearProgress,
    Stack,
    Typography,
} from "@mui/material";
import {Visibility, VisibilityOff} from "@mui/icons-material";
import PageShell from "./PageShell";
import zxcvbn from 'zxcvbn';

const strengthColors = ["#d32f2f", "#f57c00", "#fbc02d", "#388e3c", "#1b5e20"];
const strengthLabels = ["Very weak", "Weak", "Fair", "Strong", "Very strong"];

export default function SecuritySettings() {
    useEffect(() => {
        document.title = "Security Settings | Browsing Platform";
        loadStatus();
    }, []);

    const [backupCodesRemaining, setBackupCodesRemaining] = useState<number | null>(null);
    const [statusLoading, setStatusLoading] = useState(true);

    // Change password form
    const [currentPwd, setCurrentPwd] = useState("");
    const [newPwd, setNewPwd] = useState("");
    const [confirmPwd, setConfirmPwd] = useState("");
    const [totpCode, setTotpCode] = useState("");
    const [showCurrent, setShowCurrent] = useState(false);
    const [showNew, setShowNew] = useState(false);
    const [pwdBusy, setPwdBusy] = useState(false);
    const [pwdError, setPwdError] = useState<string | null>(null);
    const [pwdSuccess, setPwdSuccess] = useState(false);
    const passwordStrength = newPwd ? zxcvbn(newPwd) : null;

    // Regenerate backup codes dialog
    const [regenDialogOpen, setRegenDialogOpen] = useState(false);
    const [regenTotpCode, setRegenTotpCode] = useState("");
    const [regenBusy, setRegenBusy] = useState(false);
    const [regenError, setRegenError] = useState<string | null>(null);
    const [newBackupCodes, setNewBackupCodes] = useState<string[]>([]);

    const loadStatus = async () => {
        setStatusLoading(true);
        try {
            const res = await server.get("user/security-status");
            setBackupCodesRemaining(res?.backup_codes_remaining ?? 0);
        } catch (e) {}
        finally { setStatusLoading(false); }
    };

    const submitChangePassword = async () => {
        if (pwdBusy) return;
        if (passwordStrength && passwordStrength.score < 3) {
            setPwdError("Password is too weak. Please choose a stronger password.");
            return;
        }
        if (newPwd !== confirmPwd) {
            setPwdError("New passwords do not match.");
            return;
        }
        setPwdBusy(true);
        setPwdError(null);
        setPwdSuccess(false);
        try {
            const res = await server.post("user/change-password", {
                current_password: currentPwd,
                new_password: newPwd,
                totp_code: totpCode,
            }, undefined, {ignoreErrors: true});
            if (res?.token) {
                cookie.set('token', res.token, {
                    expires: 30,
                    sameSite: 'strict',
                    secure: window.location.protocol === 'https:',
                });
                setPwdSuccess(true);
                setCurrentPwd(""); setNewPwd(""); setConfirmPwd(""); setTotpCode("");
            } else {
                setPwdError(res?.detail || res?.error || 'An unknown error occurred');
            }
        } catch (e: any) {
            setPwdError(e?.message || 'An unknown error occurred');
        } finally {
            setPwdBusy(false);
        }
    };

    const submitRegenBackupCodes = async () => {
        if (regenBusy) return;
        setRegenBusy(true);
        setRegenError(null);
        try {
            const res = await server.post("2fa/backup-codes/regenerate", {
                totp_code: regenTotpCode,
            }, undefined, {ignoreErrors: true});
            if (res?.backup_codes) {
                setNewBackupCodes(res.backup_codes);
                setBackupCodesRemaining(res.backup_codes.length);
                setRegenTotpCode("");
            } else {
                setRegenError(res?.detail || res?.error || 'Invalid code');
            }
        } catch (e: any) {
            setRegenError(e?.message || 'Invalid code');
        } finally {
            setRegenBusy(false);
        }
    };

    const closeRegenDialog = () => {
        setRegenDialogOpen(false);
        setRegenTotpCode("");
        setRegenError(null);
        setNewBackupCodes([]);
    };

    return (
        <PageShell title="Security Settings" subtitle={null}>
            {/* Change Password */}
            <Stack gap={2}>
                <Typography variant="h6">Change Password</Typography>
                <Typography variant="body2" color="text.secondary">
                    Minimum 14 characters. Must include uppercase, lowercase, digits, and a special character.
                </Typography>
                {pwdSuccess && <Alert severity="success">Password updated successfully.</Alert>}
                {pwdError && <Alert severity="error" onClose={() => setPwdError(null)}>{pwdError}</Alert>}
                <FormControl variant="standard" sx={{maxWidth: 400}}>
                    <InputLabel>Current Password</InputLabel>
                    <Input
                        type={showCurrent ? "text" : "password"}
                        value={currentPwd}
                        onChange={(e) => setCurrentPwd(e.target.value)}
                        endAdornment={
                            <IconButton size="small" onClick={() => setShowCurrent(p => !p)}>
                                {showCurrent ? <VisibilityOff/> : <Visibility/>}
                            </IconButton>
                        }
                    />
                </FormControl>
                <FormControl variant="standard" sx={{maxWidth: 400}}>
                    <InputLabel>New Password</InputLabel>
                    <Input
                        type={showNew ? "text" : "password"}
                        value={newPwd}
                        onChange={(e) => setNewPwd(e.target.value)}
                        endAdornment={
                            <IconButton size="small" onClick={() => setShowNew(p => !p)}>
                                {showNew ? <VisibilityOff/> : <Visibility/>}
                            </IconButton>
                        }
                    />
                </FormControl>
                {newPwd.length > 0 && passwordStrength && (
                    <Box sx={{maxWidth: 400}}>
                        <LinearProgress
                            variant="determinate"
                            value={(passwordStrength.score / 4) * 100}
                            sx={{
                                height: 6, borderRadius: 3,
                                "& .MuiLinearProgress-bar": {
                                    backgroundColor: strengthColors[passwordStrength.score],
                                }
                            }}
                        />
                        <Typography sx={{fontSize: "0.8em", color: strengthColors[passwordStrength.score], mt: 0.5}}>
                            {strengthLabels[passwordStrength.score]}
                        </Typography>
                    </Box>
                )}
                <FormControl variant="standard" sx={{maxWidth: 400}}>
                    <InputLabel>Confirm New Password</InputLabel>
                    <Input
                        type="password"
                        value={confirmPwd}
                        onChange={(e) => setConfirmPwd(e.target.value)}
                    />
                </FormControl>
                <FormControl variant="standard" sx={{maxWidth: 400}}>
                    <InputLabel>Authenticator Code</InputLabel>
                    <Input
                        value={totpCode}
                        inputProps={{inputMode: "numeric", maxLength: 6}}
                        onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))}
                    />
                </FormControl>
                {pwdBusy
                    ? <CircularProgress size={24}/>
                    : <Box>
                        <Button
                            variant="contained"
                            disabled={
                                !currentPwd || newPwd.length < 14
                                || !passwordStrength || passwordStrength.score < 3
                                || newPwd !== confirmPwd || totpCode.length !== 6
                            }
                            onClick={submitChangePassword}
                        >
                            Update Password
                        </Button>
                    </Box>
                }
            </Stack>

            {/* Backup Codes */}
            <Stack gap={2}>
                <Typography variant="h6">Backup Codes</Typography>
                <Typography variant="body2" color="text.secondary">
                    Backup codes can be used in place of your authenticator app. Each code is single-use.
                </Typography>
                {statusLoading
                    ? <CircularProgress size={20}/>
                    : <Typography>
                        Remaining unused codes: <strong>{backupCodesRemaining ?? "—"}</strong>
                    </Typography>
                }
                <Box>
                    <Button variant="outlined" onClick={() => setRegenDialogOpen(true)}>
                        Regenerate Backup Codes
                    </Button>
                </Box>
            </Stack>

            {/* Regenerate Dialog */}
            <Dialog open={regenDialogOpen} onClose={closeRegenDialog} maxWidth="xs" fullWidth>
                <DialogTitle>Regenerate Backup Codes</DialogTitle>
                <DialogContent>
                    <Stack gap={2} sx={{mt: 1}}>
                        {newBackupCodes.length === 0 ? (
                            <>
                                <Typography variant="body2">
                                    This will invalidate your existing backup codes and generate 8 new ones.
                                    Enter your authenticator code to confirm.
                                </Typography>
                                {regenError && <Alert severity="error">{regenError}</Alert>}
                                <FormControl variant="standard" fullWidth>
                                    <InputLabel>Authenticator Code</InputLabel>
                                    <Input
                                        value={regenTotpCode}
                                        inputProps={{inputMode: "numeric", maxLength: 6}}
                                        onChange={(e) => setRegenTotpCode(e.target.value.replace(/\D/g, ""))}
                                    />
                                </FormControl>
                            </>
                        ) : (
                            <>
                                <Alert severity="warning">
                                    Save these codes now — they will not be shown again.
                                </Alert>
                                <Box sx={{
                                    background: "rgba(0,0,0,0.05)",
                                    border: "1px solid rgba(0,0,0,0.15)",
                                    borderRadius: "8px",
                                    padding: "12px",
                                }}>
                                    <Stack gap={0.5}>
                                        {newBackupCodes.map((code, i) => (
                                            <Typography key={i} sx={{fontFamily: "monospace", fontSize: "1.1em"}}>
                                                {code}
                                            </Typography>
                                        ))}
                                    </Stack>
                                </Box>
                            </>
                        )}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    {newBackupCodes.length === 0 ? (
                        <>
                            <Button onClick={closeRegenDialog}>Cancel</Button>
                            <Button
                                variant="contained"
                                disabled={regenTotpCode.length !== 6 || regenBusy}
                                onClick={submitRegenBackupCodes}
                            >
                                {regenBusy ? <CircularProgress size={18}/> : "Regenerate"}
                            </Button>
                        </>
                    ) : (
                        <Button variant="contained" onClick={closeRegenDialog}>
                            I've saved these codes
                        </Button>
                    )}
                </DialogActions>
            </Dialog>
        </PageShell>
    );
}
