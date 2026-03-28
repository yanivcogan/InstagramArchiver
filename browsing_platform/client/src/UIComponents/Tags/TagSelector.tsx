import React, {useState} from 'react';
import Chip from '@mui/material/Chip';
import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import Stack from '@mui/material/Stack';
import {lookupTags} from "../../services/DataFetcher";
import {ITagWithType} from "../../types/tags";
import {Button, Dialog, DialogActions, DialogContent, DialogTitle, Tooltip, Typography} from "@mui/material";

interface IProps {
    selectedTags: ITagWithType[]
    readOnly?: boolean
    onChange: (tags: ITagWithType[]) => void
    onChipClick?: (tag: ITagWithType) => void
    label?: string
}

export default function TagSelector({selectedTags, readOnly, onChange, onChipClick, label = 'Tags'}: IProps) {
    const [inputValue, setInputValue] = useState('');
    const [fetchingOptions, setFetchingOptions] = useState(false);
    const [options, setOptions] = useState<ITagWithType[]>([]);
    const [pendingDelete, setPendingDelete] = useState<{tag: ITagWithType; onDelete: (e: any) => void} | null>(null);

    const fetchMatchingOptions = async (value: string) => {
        setFetchingOptions(true);
        const matchingOptions = await lookupTags(value);
        setOptions([...matchingOptions].sort(
            (a, b) => (a.tag_type_name ?? '').localeCompare(b.tag_type_name ?? '')
                || a.name.localeCompare(b.name)
        ));
        setFetchingOptions(false);
    };

    return <><Autocomplete
        value={selectedTags}
        onChange={(_, newValue) => {
            onChange(newValue);
        }}
        disabled={readOnly === true}
        inputValue={inputValue}
        onInputChange={async (_, newInputValue) => {
            setInputValue(newInputValue);
            await fetchMatchingOptions(newInputValue);
        }}
        multiple
        noOptionsText={fetchingOptions ? 'Loading…' : (inputValue ? 'No tags found' : 'Start typing to search tags')}
        isOptionEqualToValue={(option, value) => option.id === value.id}
        getOptionLabel={(option) => option.name}
        groupBy={(option) => option.tag_type_name ?? '(No type)'}
        options={options}
        loading={fetchingOptions}
        renderTags={(value: readonly ITagWithType[], getItemProps) =>
            value.map((option: ITagWithType, index: number) => {
                const {key, onDelete, ...itemProps} = getItemProps({index});
                return (
                    <Tooltip
                        arrow
                        disableInteractive
                        title={
                            <Stack>
                                <Typography variant={"caption"}>{option.tag_type_name}</Typography>
                                {option.description && <Typography variant={"body1"}>{option.description}</Typography>}
                                {option.assignment_notes && <Typography variant={"body2"} sx={{fontStyle: 'italic'}}>{option.assignment_notes}</Typography>}
                            </Stack>
                        }
                    >
                        <Chip
                            variant={option.assignment_notes ? "filled" : "outlined"}
                            label={option.name}
                            key={key}
                            {...itemProps}
                            onDelete={() => setPendingDelete({tag: option, onDelete})}
                            onClick={onChipClick ? () => onChipClick(option) : undefined}
                        />
                    </Tooltip>
                );
            })
        }
        renderInput={(params) => (
            <TextField {...params} variant="filled" label={
                <Stack direction={"row"} alignItems={"center"} gap={1}>
                    <Typography>{label}</Typography>
                </Stack>
            }/>
        )}
    />
    <Dialog open={pendingDelete !== null} onClose={() => setPendingDelete(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Remove tag?</DialogTitle>
        <DialogContent>
            <Typography>Remove "<strong>{pendingDelete?.tag.name}</strong>"?</Typography>
        </DialogContent>
        <DialogActions>
            <Button onClick={() => setPendingDelete(null)}>Cancel</Button>
            <Button color="error" variant="contained" onClick={() => {
                pendingDelete?.onDelete(undefined);
                setPendingDelete(null);
            }}>Remove</Button>
        </DialogActions>
    </Dialog>
</>;
}
