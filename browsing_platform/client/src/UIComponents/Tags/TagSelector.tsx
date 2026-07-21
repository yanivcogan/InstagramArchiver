import React, {useRef, useState} from 'react';
import Chip from '@mui/material/Chip';
import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import Stack from '@mui/material/Stack';
import {lookupTags} from "../../services/DataFetcher";
import {ITagWithType} from "../../types/tags";
import {E_ENTITY_TYPES} from "../../types/entities";
import {Button, Dialog, DialogActions, DialogContent, DialogTitle, Tooltip, Typography} from "@mui/material";
import CreateTagDialog from "./CreateTagDialog";
import {canOfferCreate, CreateOptionRow, isCreateOption, makeCreateOption, TCreateOption} from "./createTagOption";

// The create option is a separate union member (not a fake ITagWithType), so every
// consumer of an option is forced to narrow with isCreateOption at compile time.
type TTagOption = ITagWithType | TCreateOption;

const CREATE_GROUP = 'Create new';

const isOptionEqualToValue = (option: TTagOption, value: TTagOption) =>
    isCreateOption(option) || isCreateOption(value)
        ? isCreateOption(option) && isCreateOption(value)
        : option.id === value.id;
const getOptionLabel = (option: TTagOption) => isCreateOption(option) ? option.inputValue : option.name;
const groupBy = (option: TTagOption) => isCreateOption(option) ? CREATE_GROUP : (option.tag_type_name ?? '(No type)');

const renderOption = (props: React.HTMLAttributes<HTMLLIElement> & {key?: string}, option: TTagOption) => {
    const {key, ...rest} = props;
    return (
        <li key={isCreateOption(option) ? '__create' : option.id} {...rest}>
            {isCreateOption(option)
                ? <CreateOptionRow text={`Add new: "${option.inputValue}"`}/>
                : option.name}
        </li>
    );
};

interface IProps {
    selectedTags: ITagWithType[]
    readOnly?: boolean
    onChange: (tags: ITagWithType[]) => void
    onChipClick?: (tag: ITagWithType) => void
    label?: string
    entity?: E_ENTITY_TYPES
    rapidPrefixSelection?: boolean
    disableDeletionCheck?: boolean
    single?: boolean
    disableCreate?: boolean
}

export default function TagSelector({selectedTags, readOnly, onChange, onChipClick, label = 'Tags', entity, rapidPrefixSelection = false, disableDeletionCheck = false, single = false, disableCreate = false}: IProps) {
    const [inputValue, setInputValue] = useState('');
    const [fetchingOptions, setFetchingOptions] = useState(false);
    const [options, setOptions] = useState<ITagWithType[]>([]);
    const [pendingDelete, setPendingDelete] = useState<{tag: ITagWithType; onDelete: (e: any) => void} | null>(null);
    const [createDialog, setCreateDialog] = useState<{name: string} | null>(null);
    // The query string the current `options` were fetched for; the create option is only
    // offered when the options actually correspond to the typed input, so an in-flight or
    // stale lookup can't suppress "Loading…" or offer creating a tag that already exists.
    const [optionsQuery, setOptionsQuery] = useState<string | null>(null);
    const selectedSinceLastInput = useRef(false);
    const fetchSeq = useRef(0);

    const filterOptions = (opts: TTagOption[], state: {inputValue: string}) => {
        if (disableCreate || optionsQuery !== state.inputValue) return opts;
        const realTags = opts.filter((o): o is ITagWithType => !isCreateOption(o));
        if (!canOfferCreate(state.inputValue, realTags)) return opts;
        return [...opts, makeCreateOption(state.inputValue)];
    };

    const handleCreated = (tag: ITagWithType) => {
        setCreateDialog(null);
        setInputValue('');
        setOptions([]);
        setOptionsQuery(null);
        selectedSinceLastInput.current = false;
        onChange(single ? [tag] : [...selectedTags, tag]);
    };

    const handleCreateCancelled = () => {
        // Selecting the create option triggered MUI's selection side effects (input reset,
        // blur-close) even though nothing was selected — restore the typed text so the
        // user can re-edit instead of retyping.
        const name = createDialog?.name ?? '';
        setCreateDialog(null);
        selectedSinceLastInput.current = false;
        setInputValue(name);
        if (name) void fetchMatchingOptions(name);
    };

    const createDialogNode = createDialog && (
        <CreateTagDialog
            open
            initialName={createDialog.name}
            entity={entity}
            onClose={handleCreateCancelled}
            onCreated={handleCreated}
        />
    );

    const fetchMatchingOptions = async (value: string) => {
        const seq = ++fetchSeq.current;
        setFetchingOptions(true);
        const matchingOptions = await lookupTags(value, entity);
        if (seq !== fetchSeq.current) return; // superseded by a newer lookup
        setOptions([...matchingOptions].sort(
            (a, b) => (a.tag_type_name ?? '').localeCompare(b.tag_type_name ?? '')
                || a.name.localeCompare(b.name)
        ));
        setOptionsQuery(value);
        setFetchingOptions(false);
    };

    const noOptionsText = fetchingOptions ? 'Loading…' : (inputValue ? 'No tags found' : 'Start typing to search tags');

    if (single) {
        return (
            <><Autocomplete<TTagOption, false, false, false>
                value={selectedTags[0] ?? null}
                onChange={(_, newValue) => {
                    if (newValue && isCreateOption(newValue)) {
                        setCreateDialog({name: newValue.inputValue});
                        return;
                    }
                    onChange(newValue ? [newValue] : []);
                }}
                disabled={readOnly === true}
                filterOptions={filterOptions}
                inputValue={inputValue}
                onInputChange={async (_, newInputValue, reason) => {
                    // Sync the controlled input for every reason (incl. 'reset' on
                    // select and 'clear'); otherwise it stays stuck on the typed
                    // prefix instead of the picked tag's name. Fetch only on typing.
                    setInputValue(newInputValue);
                    if (reason === 'input') await fetchMatchingOptions(newInputValue);
                }}
                onClose={() => {
                    setOptions([]);
                    setOptionsQuery(null);
                }}
                noOptionsText={noOptionsText}
                isOptionEqualToValue={isOptionEqualToValue}
                getOptionLabel={getOptionLabel}
                groupBy={groupBy}
                options={options}
                loading={fetchingOptions}
                renderOption={renderOption}
                renderInput={(params) => (
                    <TextField {...params} variant="filled" label={label}/>
                )}
            />
            {createDialogNode}</>
        );
    }

    return <><Autocomplete<TTagOption, true, false, false>
        value={selectedTags}
        onChange={(_, newValue) => {
            const created = newValue.find(isCreateOption);
            if (created) {
                setCreateDialog({name: created.inputValue});
                return;
            }
            onChange(newValue.filter((o): o is ITagWithType => !isCreateOption(o)));
        }}
        disabled={readOnly === true}
        disableCloseOnSelect={rapidPrefixSelection}
        filterOptions={filterOptions}
        inputValue={inputValue}
        onInputChange={async (_, newInputValue, reason) => {
            if (rapidPrefixSelection && reason !== 'input') {
                if (reason === 'selectOption') selectedSinceLastInput.current = true;
                return;
            }
            selectedSinceLastInput.current = false;
            setInputValue(newInputValue);
            // Fetch only on typing — selection resets ('' / 'reset') shouldn't fire a lookup.
            if (reason === 'input') await fetchMatchingOptions(newInputValue);
        }}
        onClose={() => {
            if (rapidPrefixSelection && selectedSinceLastInput.current) {
                setInputValue('');
                setOptions([]);
                setOptionsQuery(null);
                selectedSinceLastInput.current = false;
            }
        }}
        multiple
        noOptionsText={noOptionsText}
        isOptionEqualToValue={isOptionEqualToValue}
        getOptionLabel={getOptionLabel}
        groupBy={groupBy}
        options={options}
        loading={fetchingOptions}
        renderOption={renderOption}
        renderTags={(value: readonly TTagOption[], getItemProps) =>
            value.map((option: TTagOption, index: number) => {
                if (isCreateOption(option)) return null; // never committed to the value; narrow for the compiler
                const {key, onDelete, ...itemProps} = getItemProps({index});
                return (
                    <Tooltip
                        key={key}
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
                            {...itemProps}
                            onDelete={() => {
                                if(disableDeletionCheck){
                                    onDelete(undefined)
                                }
                                else {
                                    setPendingDelete({tag: option, onDelete})
                                }
                            }}
                            onClick={onChipClick ? () => onChipClick(option) : undefined}
                        />
                    </Tooltip>
                );
            })
        }
        renderInput={(params) => (
            <TextField {...params} variant="filled" label={label}/>
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
    {createDialogNode}
</>;
}
