import React from 'react';
import {FormControlLabel, Switch} from '@mui/material';
import {ImmutableTree, MuiConfig, Utils} from '@react-awesome-query-builder/mui';
import {ADVANCED_FILTERS_CONFIG} from '../../services/DataFetcher';

const config = {...MuiConfig, fields: ADVANCED_FILTERS_CONFIG['accounts']};

const POST_COUNT_RULE = {">" : [{"var": "post_count"}, 0]};

function isPostCountRule(rule: any): boolean {
    return (
        rule?.[">"] != null &&
        Array.isArray(rule[">"]) &&
        rule[">"][0]?.var === "post_count" &&
        rule[">"][1] === 0
    );
}

function containsPostCountRule(logic: any): boolean {
    if (!logic) return false;
    if (isPostCountRule(logic)) return true;
    if (Array.isArray(logic.and)) return logic.and.some(containsPostCountRule);
    return false;
}

function addPostCountRule(logic: any): any {
    if (!logic) return POST_COUNT_RULE;
    if (Array.isArray(logic.and)) return {"and": [...logic.and, POST_COUNT_RULE]};
    return {"and": [logic, POST_COUNT_RULE]};
}

function removePostCountRule(logic: any): any {
    if (!logic || isPostCountRule(logic)) return null;
    if (Array.isArray(logic.and)) {
        const filtered = logic.and.filter((item: any) => !isPostCountRule(item));
        if (filtered.length === 0) return null;
        if (filtered.length === 1) return filtered[0];
        return {"and": filtered};
    }
    return logic;
}

export interface SearchShortcutsProps {
    tree: ImmutableTree;
    onChange: (newLogic: any) => void;
}

export default function AccountSearchShortcuts({tree, onChange}: SearchShortcutsProps) {
    const logic = Utils.Export.jsonLogicFormat(tree, config).logic;
    const isHiding = containsPostCountRule(logic);

    const handleToggle = () => {
        const newLogic = isHiding ? removePostCountRule(logic) : addPostCountRule(logic);
        onChange(newLogic);
    };

    return (
        <FormControlLabel
            control={<Switch checked={isHiding} onChange={handleToggle} size="small"/>}
            label="Hide accounts with no posts"
        />
    );
}
