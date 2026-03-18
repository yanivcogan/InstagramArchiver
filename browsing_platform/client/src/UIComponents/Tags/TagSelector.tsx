import React, {useState} from 'react';
import Chip from '@mui/material/Chip';
import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import Stack from '@mui/material/Stack';
import {lookupTags} from "../../services/DataFetcher";
import {ITagWithType} from "../../types/tags";
import {Tooltip, Typography} from "@mui/material";

interface IProps {
    selectedTags: ITagWithType[]
    readOnly?: boolean
    onChange: (tags: ITagWithType[]) => void
}

export default function TagSelector({selectedTags: initialTags, readOnly, onChange}: IProps) {
    const [inputValue, setInputValue] = useState('');
    const [fetchingOptions, setFetchingOptions] = useState(false);
    const [options, setOptions] = useState<ITagWithType[]>([]);
    const [selectedTags, setSelectedTags] = useState(initialTags);

    const fetchMatchingOptions = async (value: string) => {
        setFetchingOptions(true);
        const matchingOptions = await lookupTags(value);
        setOptions(matchingOptions);
        setFetchingOptions(false);
    };

    return <Autocomplete
        value={selectedTags}
        onChange={(_, newValue) => {
            setSelectedTags(newValue);
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
        isOptionEqualToValue={(option, value) => option.name === value.name}
        getOptionLabel={(option) => option.name}
        options={options}
        loading={fetchingOptions}
        renderTags={(value: readonly ITagWithType[], getItemProps) =>
            value.map((option: ITagWithType, index: number) => {
                const {key, ...itemProps} = getItemProps({index});
                return (
                    <Tooltip
                        arrow
                        disableInteractive
                        title={
                            <Stack>
                                <Typography variant={"caption"}>{option.tag_type_name}</Typography>
                                <Typography variant={"body1"}>{option.description}</Typography>
                            </Stack>
                        }
                    >
                        <Chip variant="outlined" label={option.name} key={key} {...itemProps} />
                    </Tooltip>
                );
            })
        }
        renderInput={(params) => (
            <TextField {...params} variant="filled" label="Tags"/>
        )}
    />;
}
