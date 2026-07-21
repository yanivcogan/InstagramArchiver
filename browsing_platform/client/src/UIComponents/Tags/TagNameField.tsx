import React from 'react';
import TextField from '@mui/material/TextField';

// Mirrors the server-side TagBody validator: non-empty, no commas.
export const isValidTagName = (name: string) => !!name.trim() && !name.includes(',');

interface IProps {
    value: string;
    onChange: (value: string) => void;
    autoFocus?: boolean;
}

/** Tag name input with the shared comma-validation UI used by every tag-creation form. */
export default function TagNameField({value, onChange, autoFocus = false}: IProps) {
    return (
        <TextField
            label="Name"
            value={value}
            onChange={e => onChange(e.target.value)}
            error={value.includes(',')}
            helperText={value.includes(',') ? 'Tag name cannot contain commas' : undefined}
            required
            autoFocus={autoFocus}
        />
    );
}
