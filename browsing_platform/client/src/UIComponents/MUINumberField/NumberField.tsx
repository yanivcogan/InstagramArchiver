import React, {ChangeEvent, useEffect, useState} from 'react';
import TextField, {TextFieldProps} from '@mui/material/TextField';
import InputAdornment from '@mui/material/InputAdornment';
import IconButton from '@mui/material/IconButton';
import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';

interface NumberFieldProps extends Omit<TextFieldProps, 'type' | 'onChange' | 'value'> {
    value?: number;
    onChange?: (event: ChangeEvent<HTMLInputElement>, value: number | null) => void;
    min?: number;
    max?: number;
    step?: number;
}

export function NumberField({value: valueProp, onChange, min, max, step = 1, slotProps: propsSlotProps, ...rest}: NumberFieldProps) {
    const [value, setValue] = useState(
        valueProp !== undefined && valueProp !== null ? String(valueProp) : ''
    );

    useEffect(() => {
        if (valueProp !== undefined && valueProp !== null && valueProp !== Number(value)) {
            setValue(String(valueProp));
        }
    }, [valueProp]);

    const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
        let val = event.target.value;
        if (/^-?\d*\.?\d*$/.test(val)) {
            if (val.length > 1 && val[0] === '0' && val[1] !== '.') {
                val = val.replace(/^0+/, '');
            }
            setValue(val);
            const num = val === '' || val === '-' || val === '.' ? null : Number(val);
            if (onChange) {
                if (num !== null) {
                    let bounded = num;
                    if (min !== undefined && bounded < min) bounded = min;
                    if (max !== undefined && bounded > max) bounded = max;
                    onChange(event, bounded);
                } else {
                    onChange(event, null);
                }
            }
        }
    };

    const handleStep = (direction: 1 | -1) => {
        let current = Number(value);
        if (isNaN(current)) current = 0;
        let next = current + direction * (step ?? 1);
        next = Math.round((next + Number.EPSILON) * 100) / 100;
        if (min !== undefined && next < min) next = min;
        if (max !== undefined && next > max) next = max;
        setValue(String(next));
        if (onChange) {
            const syntheticEvent = {target: {value: String(next)}} as ChangeEvent<HTMLInputElement>;
            onChange(syntheticEvent, next);
        }
    };

    return (
        <TextField
            {...rest}
            type="text"
            value={value}
            onChange={handleInputChange}
            slotProps={{
                ...propsSlotProps,
                htmlInput: {
                    inputMode: 'decimal',
                    pattern: '[0-9]*',
                    min,
                    max,
                    step,
                    ...(propsSlotProps?.htmlInput as object),
                },
                input: {
                    ...(propsSlotProps?.input as object),
                    endAdornment: (
                        <InputAdornment position="end">
                            <IconButton
                                aria-label="decrement"
                                onClick={() => handleStep(-1)}
                                size="small"
                                disabled={min !== undefined && Number(value) <= min}
                            >
                                <RemoveIcon fontSize="small"/>
                            </IconButton>
                            <IconButton
                                aria-label="increment"
                                onClick={() => handleStep(1)}
                                size="small"
                                disabled={max !== undefined && Number(value) >= max}
                            >
                                <AddIcon fontSize="small"/>
                            </IconButton>
                        </InputAdornment>
                    ),
                },
            }}
        />
    );
}

export default NumberField;
