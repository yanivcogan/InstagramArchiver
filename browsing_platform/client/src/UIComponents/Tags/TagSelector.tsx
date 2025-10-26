import * as React from 'react';
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

interface IState {
    inputValue: string,
    fetchingOptions: boolean,
    options: ITagWithType[],
    selectedTags: ITagWithType[],
}

export default class TagSelector extends React.Component <IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = {
            inputValue: '',
            selectedTags: props.selectedTags,
            fetchingOptions: false,
            options: [],
        };
    }

    fetchMatchingOptions = async () => {
        this.setState((curr) => ({...curr, fetchingOptions: true}), async () => {
                const inputValue = this.state.inputValue;
                const matchingOptions = await lookupTags(inputValue);
                this.setState((curr) => ({...curr, options: matchingOptions, fetchingOptions: false}));
            }
        )
    };

    render() {
        const {options, fetchingOptions} = this.state;
        return <Autocomplete
            value={this.state.selectedTags}
            onChange={(_, newValue) => {
                this.setState({selectedTags: newValue});
                this.props.onChange(newValue);
            }}
            disabled={this.props.readOnly === true}
            inputValue={this.state.inputValue}
            onInputChange={async (_, newInputValue) => {
                this.setState({inputValue: newInputValue}, this.fetchMatchingOptions);
            }}
            multiple
            noOptionsText={fetchingOptions ? 'Loading…' : (this.state.inputValue ? 'No tags found' : 'Start typing to search tags')}
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
                <TextField
                    {...params}
                    variant="filled"
                    label="Tags"
                />
            )}
        />;
    }
}