import React, {useState} from 'react';
import {Box, Chip, Stack, ToggleButton, ToggleButtonGroup, Typography} from "@mui/material";
import {ITagWithType} from "../../types/tags";
import {lookupTags} from "../../services/DataFetcher";
import Autocomplete from "@mui/material/Autocomplete";
import TextField from "@mui/material/TextField";

interface IProps {
    tagIds: number[];
    tagFilterMode: "any" | "all";
    selectedTagObjects: ITagWithType[];
    onChange: (tagIds: number[], mode: "any" | "all", tagObjects: ITagWithType[]) => void;
}

export default function TagFilterBar({tagIds, tagFilterMode, selectedTagObjects, onChange}: IProps) {
    const [inputValue, setInputValue] = useState('');
    const [options, setOptions] = useState<ITagWithType[]>([]);
    const [fetching, setFetching] = useState(false);

    const fetchOptions = async (value: string) => {
        setFetching(true);
        const results = await lookupTags(value);
        setOptions(results);
        setFetching(false);
    };

    const handleTagsChange = (newTags: ITagWithType[]) => {
        onChange(newTags.map(t => t.id), tagFilterMode, newTags);
    };

    const handleModeChange = (_: React.MouseEvent, newMode: "any" | "all" | null) => {
        if (newMode) onChange(tagIds, newMode, selectedTagObjects);
    };

    return (
        <Stack direction="row" gap={2} alignItems="center" flexWrap="wrap">
            <Typography variant="body2" sx={{color: 'text.secondary', whiteSpace: 'nowrap'}}>
                Filter by tag:
            </Typography>
            <Box sx={{minWidth: 260, flex: 1}}>
                <Autocomplete
                    multiple
                    size="small"
                    value={selectedTagObjects}
                    onChange={(_, newValue) => handleTagsChange(newValue)}
                    inputValue={inputValue}
                    onInputChange={async (_, newInputValue) => {
                        setInputValue(newInputValue);
                        if (newInputValue) await fetchOptions(newInputValue);
                    }}
                    isOptionEqualToValue={(opt, val) => opt.id === val.id}
                    getOptionLabel={(opt) => opt.tag_type_name ? `${opt.tag_type_name} / ${opt.name}` : opt.name}
                    options={options}
                    loading={fetching}
                    noOptionsText={fetching ? 'Loading…' : (inputValue ? 'No tags found' : 'Type to search tags')}
                    renderTags={(value, getItemProps) =>
                        value.map((tag, index) => {
                            const {key, ...itemProps} = getItemProps({index});
                            return <Chip key={key} label={tag.name} size="small" {...itemProps} />;
                        })
                    }
                    renderInput={(params) => (
                        <TextField {...params} variant="outlined" placeholder="Search tags…"/>
                    )}
                />
            </Box>
            {selectedTagObjects.length > 1 && (
                <ToggleButtonGroup
                    size="small"
                    exclusive
                    value={tagFilterMode}
                    onChange={handleModeChange}
                >
                    <ToggleButton value="any">Match Any</ToggleButton>
                    <ToggleButton value="all">Match All</ToggleButton>
                </ToggleButtonGroup>
            )}
        </Stack>
    );
}
