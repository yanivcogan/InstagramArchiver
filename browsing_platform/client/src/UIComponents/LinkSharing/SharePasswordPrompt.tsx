import React, {useState} from 'react';
import {
    Box,
    Button,
    CircularProgress,
    IconButton,
    InputAdornment,
    Paper,
    TextField,
    Typography,
} from '@mui/material';
import {Lock, Visibility, VisibilityOff} from '@mui/icons-material';
import {setSharePasswordToken, verifySharePassword} from '../../services/linkSharing';

interface IProps {
    linkSuffix: string;
    onUnlocked: () => void;
}

export default function SharePasswordPrompt({linkSuffix, onUnlocked}: IProps) {
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        const token = await verifySharePassword(linkSuffix, password);
        if (token) {
            setSharePasswordToken(linkSuffix, token);
            onUnlocked();
        } else {
            setError('Incorrect password. Please try again.');
        }
        setLoading(false);
    };

    return (
        <Box
            sx={{
                minHeight: '100vh',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                bgcolor: 'grey.100',
                p: 2,
            }}
        >
            <Paper elevation={3} sx={{p: 4, maxWidth: 360, width: '100%', textAlign: 'center'}}>
                <Lock sx={{fontSize: 48, color: 'text.secondary', mb: 2}}/>
                <Typography variant="h6" gutterBottom>Password required</Typography>
                <Typography variant="body2" color="text.secondary" sx={{mb: 3}}>
                    This link is password-protected. Enter the password to view the content.
                </Typography>
                <form onSubmit={handleSubmit} autoComplete="off">
                    <TextField
                        fullWidth
                        label="Password"
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        error={!!error}
                        helperText={error}
                        autoFocus
                        inputProps={{autoComplete: 'new-password'}}
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    <IconButton
                                        onClick={() => setShowPassword(v => !v)}
                                        edge="end"
                                        size="small"
                                    >
                                        {showPassword ? <VisibilityOff/> : <Visibility/>}
                                    </IconButton>
                                </InputAdornment>
                            ),
                        }}
                        sx={{mb: 2}}
                    />
                    <Button
                        fullWidth
                        variant="contained"
                        type="submit"
                        disabled={loading || !password}
                        startIcon={loading ? <CircularProgress size={16}/> : undefined}
                    >
                        {loading ? 'Verifying…' : 'Unlock'}
                    </Button>
                </form>
            </Paper>
        </Box>
    );
}
