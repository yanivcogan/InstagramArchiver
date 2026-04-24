import React, {useEffect, useMemo, useState} from 'react';
import {Box, Chip, Stack, ToggleButton, ToggleButtonGroup, Typography} from "@mui/material";
import {IQuickAccessData, ITagWithType} from "../../types/tags";
import {lookupTags} from "../../services/DataFetcher";
import {fetchQuickAccessData} from "../../services/TagManagementService";
import Autocomplete from "@mui/material/Autocomplete";
import TextField from "@mui/material/TextField";
import QuickAccessBar from "./QuickAccessBar";

interface IProps {
    tagIds: number[];
    tagFilterMode: "any" | "all";
    selectedTagObjects: ITagWithType[];
    onChange: (tagIds: number[], mode: "any" | "all", tagObjects: ITagWithType[]) => void;
    entity?: string;
}

export default function TagFilterBar({tagIds, tagFilterMode, selectedTagObjects, onChange, entity}: IProps) {
    const [inputValue, setInputValue] = useState('');
    const [options, setOptions] = useState<ITagWithType[]>([]);
    const [fetching, setFetching] = useState(false);
    const [quickAccessData, setQuickAccessData] = useState<IQuickAccessData>({individual_tags: [], type_dropdowns: []});

    useEffect(() => {
        let cancelled = false;
        fetchQuickAccessData(entity).then(data => { if (!cancelled) setQuickAccessData(data); }).catch(() => {});
        return () => { cancelled = true; };
    }, [entity]);

    const selectedTagIds = useMemo(() => new Set(selectedTagObjects.map(t => t.id)), [selectedTagObjects]);

    const fetchOptions = async (value: string) => {
        setFetching(true);
        const results = await lookupTags(value, entity);
        setOptions(results);
        setFetching(false);
    };

    const handleTagsChange = (newTags: ITagWithType[]) => {
        onChange(newTags.map(t => t.id), tagFilterMode, newTags);
    };

    const handleModeChange = (_: React.MouseEvent, newMode: "any" | "all" | null) => {
        if (newMode) onChange(tagIds, newMode, selectedTagObjects);
    };

    const handleQuickAccessSelect = (tag: ITagWithType) => {
        const newTags = selectedTagIds.has(tag.id)
            ? selectedTagObjects.filter(t => t.id !== tag.id)
            : [...selectedTagObjects, tag];
        onChange(newTags.map(t => t.id), tagFilterMode, newTags);
    };

    const hasQuickAccess = quickAccessData.individual_tags.length > 0 || quickAccessData.type_dropdowns.length > 0;

    return (
        <Stack direction="column" gap={1}>
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
            {hasQuickAccess && (
                <QuickAccessBar
                    quickAccessData={quickAccessData}
                    selectedTagIds={selectedTagIds}
                    onSelect={handleQuickAccessSelect}
                    variant="filter"
                />
            )}
        </Stack>
    );
}
