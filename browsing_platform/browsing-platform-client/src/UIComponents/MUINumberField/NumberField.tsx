import React, {Component, ChangeEvent} from 'react';
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

interface NumberFieldState {
    value: string;
}

export class NumberField extends Component<NumberFieldProps, NumberFieldState> {
    constructor(props: NumberFieldProps) {
        super(props);
        this.state = {
            value: props.value !== undefined && props.value !== null ? String(props.value) : '',
        };
    }

    componentDidUpdate(prevProps: NumberFieldProps) {
        if (this.props.value !== prevProps.value && this.props.value !== Number(this.state.value)) {
            this.setState({
                value: this.props.value !== undefined && this.props.value !== null ? String(this.props.value) : '',
            });
        }
    }

    handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
        const {min, max, onChange} = this.props;
        let val = event.target.value;

        // Only allow valid number input (including empty string)
        if (/^-?\d*\.?\d*$/.test(val)) {
            // Remove leading zeros
            if (val.length > 1 && val[0] === '0' && val[1] !== '.') {
                val = val.replace(/^0+/, '');
            }
            this.setState({value: val});

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

    handleStep = (direction: 1 | -1) => {
        const {min, max, step = 1, onChange} = this.props;
        let current = Number(this.state.value);
        if (isNaN(current)) current = 0;
        let next = current + direction * step;
        next = Math.round((next + Number.EPSILON) * 100) / 100; // Round to avoid floating point issues
        if (min !== undefined && next < min) next = min;
        if (max !== undefined && next > max) next = max;
        this.setState({value: String(next)});
        if (onChange) {
            // @ts-ignore
            onChange({target: {value: String(next)}}, next);
        }
    };

    render() {
        const {min, max, step, value, onChange, InputProps, ...rest} = this.props;
        return (
            <TextField
                {...rest}
                type="text"
                value={this.state.value}
                onChange={this.handleInputChange}
                inputProps={{
                    inputMode: 'decimal',
                    pattern: '[0-9]*',
                    min,
                    max,
                    step,
                    ...rest.inputProps,
                }}
                InputProps={{
                    ...InputProps,
                    endAdornment: (
                        <InputAdornment position="end">
                            <IconButton
                                aria-label="decrement"
                                onClick={() => this.handleStep(-1)}
                                size="small"
                                disabled={min !== undefined && Number(this.state.value) <= min}
                            >
                                <RemoveIcon fontSize="small"/>
                            </IconButton>
                            <IconButton
                                aria-label="increment"
                                onClick={() => this.handleStep(1)}
                                size="small"
                                disabled={max !== undefined && Number(this.state.value) >= max}
                            >
                                <AddIcon fontSize="small"/>
                            </IconButton>
                        </InputAdornment>
                    ),
                }}
            />
        );
    }
}

export default NumberField;