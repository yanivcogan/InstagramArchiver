import React, {useEffect, useState} from 'react';
import server from '../services/server';
import cookie from 'js-cookie';
import {
    Alert,
    Box,
    Button,
    CircularProgress,
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
    }, []);

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

    const submitChangePassword = async () => {
        if (pwdBusy) return;
        if (passwordStrength && passwordStrength.score < 3) {
            setPwdError("Password is too weak. Please choose a stronger password.");
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

    return (
        <PageShell title="Security Settings" subtitle={null}>
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
                        onPaste={(e) => e.preventDefault()}
                    />
                    {confirmPwd.length > 0 && newPwd !== confirmPwd && (
                        <Typography sx={{fontSize: "0.8em", color: "error.main", mt: 0.5}}>
                            Passwords do not match
                        </Typography>
                    )}
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
        </PageShell>
    );
}
