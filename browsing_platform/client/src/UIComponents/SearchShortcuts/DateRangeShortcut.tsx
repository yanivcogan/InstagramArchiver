import React from 'react';
import {Stack} from '@mui/material';
import {DatePicker} from '@mui/x-date-pickers/DatePicker';
import dayjs, {Dayjs} from 'dayjs';
import {ImmutableTree, MuiConfig, Utils} from '@react-awesome-query-builder/mui';
import {ADVANCED_FILTERS_CONFIG, T_Search_Mode} from '../../services/DataFetcher';
import {SearchShortcutsProps} from './AccountSearchShortcuts';

function isGteRule(rule: any, field: string): boolean {
    return rule?.[">="] != null && Array.isArray(rule[">="]) && rule[">="][0]?.var === field;
}

function isLteRule(rule: any, field: string): boolean {
    return rule?.["<="] != null && Array.isArray(rule["<="]) && rule["<="][0]?.var === field;
}

function extractDateBound(logic: any, field: string, op: ">=" | "<="): string | null {
    if (!logic) return null;
    const checker = op === ">=" ? isGteRule : isLteRule;
    if (checker(logic, field)) return logic[op][1] as string;
    if (Array.isArray(logic.and)) {
        for (const item of logic.and) {
            const val = extractDateBound(item, field, op);
            if (val !== null) return val;
        }
    }
    return null;
}

function removeDateBound(logic: any, field: string, op: ">=" | "<="): any {
    if (!logic) return null;
    const checker = op === ">=" ? isGteRule : isLteRule;
    if (checker(logic, field)) return null;
    if (Array.isArray(logic.and)) {
        const filtered = logic.and.filter((item: any) => !checker(item, field));
        if (filtered.length === 0) return null;
        if (filtered.length === 1) return filtered[0];
        return {"and": filtered};
    }
    return logic;
}

function setDateBound(logic: any, field: string, op: ">=" | "<=", value: string): any {
    // Remove any existing rule for this bound first, then add the new one
    const withoutOld = removeDateBound(logic, field, op);
    const newRule = {[op]: [{"var": field}, value]};
    if (!withoutOld) return newRule;
    if (Array.isArray(withoutOld.and)) return {"and": [...withoutOld.and, newRule]};
    return {"and": [withoutOld, newRule]};
}

interface DateRangeShortcutProps extends SearchShortcutsProps {
    field: string;
    mode: T_Search_Mode;
    fromLabel?: string;
    toLabel?: string;
}

function DateRangeShortcut({tree, onChange, field, mode, fromLabel = "From", toLabel = "To"}: DateRangeShortcutProps) {
    const config = {...MuiConfig, fields: ADVANCED_FILTERS_CONFIG[mode]};
    const logic = Utils.Export.jsonLogicFormat(tree, config).logic;

    const fromStr = extractDateBound(logic, field, ">=");
    const toStr = extractDateBound(logic, field, "<=");

    const fromValue: Dayjs | null = fromStr ? dayjs(fromStr) : null;
    const toValue: Dayjs | null = toStr ? dayjs(toStr) : null;

    const handleFromChange = (val: Dayjs | null) => {
        let newLogic: any;
        if (!val || !val.isValid()) {
            newLogic = removeDateBound(logic, field, ">=") ?? null;
        } else {
            newLogic = setDateBound(logic, field, ">=", val.format("YYYY-MM-DD"));
        }
        onChange(newLogic);
    };

    const handleToChange = (val: Dayjs | null) => {
        let newLogic: any;
        if (!val || !val.isValid()) {
            newLogic = removeDateBound(logic, field, "<=") ?? null;
        } else {
            newLogic = setDateBound(logic, field, "<=", val.format("YYYY-MM-DD"));
        }
        onChange(newLogic);
    };

    return (
        <Stack direction="row" spacing={2} alignItems="center">
            <DatePicker
                label={fromLabel}
                value={fromValue}
                onChange={handleFromChange}
                format="DD/MM/YYYY"
                slotProps={{textField: {size: "small"}}}
            />
            <DatePicker
                label={toLabel}
                value={toValue}
                onChange={handleToChange}
                format="DD/MM/YYYY"
                slotProps={{textField: {size: "small"}}}
            />
        </Stack>
    );
}

export function createDateRangeShortcut(
    field: string,
    mode: T_Search_Mode,
    fromLabel?: string,
    toLabel?: string,
): React.FC<SearchShortcutsProps> {
    return function DateRangeShortcutInstance({tree, onChange}: SearchShortcutsProps) {
        return <DateRangeShortcut tree={tree} onChange={onChange} field={field} mode={mode} fromLabel={fromLabel} toLabel={toLabel}/>;
    };
}
