import React, {useEffect, useRef, useState} from 'react';
import {FormControl, InputLabel, MenuItem, Select} from "@mui/material";
import CheckIcon from '@mui/icons-material/Check';
import {IQuickAccessTypeDropdown, ITagWithType} from "../../types/tags";

interface IProps {
    dropdown: IQuickAccessTypeDropdown;
    assignedTagIds: Set<number>;
    onSelect: (tag: ITagWithType) => void;
}

export default function QuickAccessTypeDropdown({dropdown, assignedTagIds, onSelect}: IProps) {
    const [minWidth, setMinWidth] = useState(0);
    const measureRef = useRef<HTMLSpanElement>(null);

    useEffect(() => {
        if (measureRef.current) {
            setMinWidth(measureRef.current.offsetWidth + 42);
        }
    }, [dropdown.type_name]);

    return (
        <>
            <span
                ref={measureRef}
                style={{
                    position: 'fixed',
                    visibility: 'hidden',
                    pointerEvents: 'none',
                    whiteSpace: 'nowrap',
                    fontSize: '0.8125rem',
                    textTransform: 'uppercase',
                }}
            >
                {dropdown.type_name}
            </span>
            <FormControl sx={{minWidth, textTransform: "uppercase"}}>
                <InputLabel
                    sx={{
                        fontSize: '0.8125rem',
                        '&:not(.MuiInputLabel-shrink)': {
                            transform: 'translate(10px, 7px) scale(1)',
                        },
                    }}
                    shrink={false}
                >
                    {dropdown.type_name}
                </InputLabel>
                <Select
                    value=""
                    onChange={(e) => {
                        const tag = dropdown.tags.find(t => t.id === Number(e.target.value));
                        if (tag) onSelect(tag);
                    }}
                    renderValue={() => ""}
                    sx={{
                        fontSize: '0.8125rem',
                        '& .MuiSelect-select': {
                            paddingTop: '6px',
                            paddingBottom: '6px',
                            paddingLeft: '10px',
                            paddingRight: '28px',
                        },
                    }}
                >
                    {dropdown.tags.map(tag => {
                        const assigned = assignedTagIds.has(tag.id);
                        return (
                            <MenuItem key={tag.id} value={tag.id} sx={{gap: 1}}>
                                <CheckIcon
                                    fontSize="small"
                                    sx={{visibility: assigned ? 'visible' : 'hidden', color: 'success.main'}}
                                />
                                {tag.name}
                            </MenuItem>
                        );
                    })}
                </Select>
            </FormControl>
        </>
    );
}
