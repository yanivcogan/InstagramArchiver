import React from 'react';
import {Stack, ToggleButton, ToggleButtonGroup} from '@mui/material';
import {MuiConfig, Utils} from '@react-awesome-query-builder/mui';
import {ADVANCED_FILTERS_CONFIG} from '../../services/DataFetcher';
import {SearchShortcutsProps} from './AccountSearchShortcuts';
import {createDateRangeShortcut} from './DateRangeShortcut';

const config = {...MuiConfig, fields: ADVANCED_FILTERS_CONFIG['media']};
const DateRange = createDateRangeShortcut('publication_date', 'media', 'Published from', 'Published to');

function isAnyMediaTypeRule(rule: any): boolean {
    return rule?.["=="] != null &&
        Array.isArray(rule["=="]) &&
        rule["=="][0]?.var === "media_type";
}

function extractMediaType(logic: any): string | null {
    if (!logic) return null;
    if (isAnyMediaTypeRule(logic)) return logic["=="][1] as string;
    if (Array.isArray(logic.and)) {
        for (const item of logic.and) {
            if (isAnyMediaTypeRule(item)) return item["=="][1] as string;
        }
    }
    return null;
}

function removeMediaTypeRule(logic: any): any {
    if (!logic) return null;
    if (isAnyMediaTypeRule(logic)) return null;
    if (Array.isArray(logic.and)) {
        const filtered = logic.and.filter((item: any) => !isAnyMediaTypeRule(item));
        if (filtered.length === 0) return null;
        if (filtered.length === 1) return filtered[0];
        return {"and": filtered};
    }
    return logic;
}

function setMediaTypeRule(logic: any, value: string): any {
    const withoutOld = removeMediaTypeRule(logic);
    const newRule = {"==": [{"var": "media_type"}, value]};
    if (!withoutOld) return newRule;
    if (Array.isArray(withoutOld.and)) return {"and": [...withoutOld.and, newRule]};
    return {"and": [withoutOld, newRule]};
}

export default function MediaSearchShortcuts({tree, onChange}: SearchShortcutsProps) {
    const logic = Utils.Export.jsonLogicFormat(tree, config).logic;
    const currentType = extractMediaType(logic);

    const handleTypeChange = (_: React.MouseEvent, value: string | null) => {
        const newLogic = (value === null || value === '')
            ? removeMediaTypeRule(logic) ?? null
            : setMediaTypeRule(logic, value);
        onChange(newLogic);
    };

    return (
        <Stack direction="row" spacing={2} alignItems="center">
            <DateRange tree={tree} onChange={onChange}/>
            <ToggleButtonGroup
                value={currentType ?? ''}
                exclusive
                onChange={handleTypeChange}
                size="small"
            >
                <ToggleButton value="">All</ToggleButton>
                <ToggleButton value="video">Video</ToggleButton>
                <ToggleButton value="image">Photo</ToggleButton>
            </ToggleButtonGroup>
        </Stack>
    );
}
