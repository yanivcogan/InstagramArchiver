import React from 'react';
import {Button, Stack, Tooltip} from "@mui/material";
import AddIcon from '@mui/icons-material/Add';
import CheckIcon from '@mui/icons-material/Check';
import FilterListIcon from '@mui/icons-material/FilterList';
import {IQuickAccessData, ITagWithType} from "../../types/tags";
import QuickAccessTypeDropdown from "./QuickAccessTypeDropdown";

interface IProps {
    quickAccessData: IQuickAccessData;
    selectedTagIds: Set<number>;
    onSelect: (tag: ITagWithType) => void;
    variant?: 'annotate' | 'filter';
}

export default function QuickAccessBar({quickAccessData, selectedTagIds, onSelect, variant = 'annotate'}: IProps) {
    const isFilter = variant === 'filter';

    return (
        <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
            {quickAccessData.individual_tags.map(qTag => {
                const active = selectedTagIds.has(qTag.id);
                const qualifier = qTag.tag_type_name ? `${qTag.tag_type_name} / ` : "";
                const tooltip = active
                    ? (isFilter ? `Remove filter: ${qTag.name}` : `Edit/remove: ${qTag.name}`)
                    : (isFilter ? `Filter by: ${qualifier}${qTag.name}` : `Quick-add: ${qualifier}${qTag.name}`);
                const InactiveIcon = isFilter ? FilterListIcon : AddIcon;
                return (
                    <Tooltip key={qTag.id} title={tooltip} disableInteractive>
                        <Button
                            variant={active ? "contained" : "outlined"}
                            size="small"
                            onClick={() => onSelect(qTag)}
                            startIcon={active ? <CheckIcon/> : <InactiveIcon/>}
                        >
                            {qTag.name}
                        </Button>
                    </Tooltip>
                );
            })}
            {quickAccessData.type_dropdowns.map(dropdown => (
                <QuickAccessTypeDropdown
                    key={dropdown.type_id}
                    dropdown={dropdown}
                    assignedTagIds={selectedTagIds}
                    onSelect={onSelect}
                />
            ))}
        </Stack>
    );
}
