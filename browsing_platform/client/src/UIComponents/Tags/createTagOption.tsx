import React from 'react';
import Stack from '@mui/material/Stack';
import AddIcon from '@mui/icons-material/Add';
import {ITagWithType} from '../../types/tags';

/** Synthetic autocomplete option offering to create a tag from the typed text.
 *  Deliberately NOT assignable to ITagWithType, so a code path that forgets to
 *  narrow with isCreateOption is a compile error rather than a fake tag leaking
 *  into consumers. */
export type TCreateOption = {inputValue: string; __create: true};

export const isCreateOption = (o: unknown): o is TCreateOption =>
    !!o && typeof o === 'object' && (o as TCreateOption).__create === true;

export const makeCreateOption = (input: string): TCreateOption => ({inputValue: input.trim(), __create: true});

// Whether typed text should offer a "create new tag" action: non-empty, comma-free, and not an existing option.
export const canOfferCreate = (raw: string, options: ITagWithType[]): boolean => {
    const t = raw.trim().toLowerCase();
    return t.length > 0 && !t.includes(',') && !options.some(o => o.name.toLowerCase() === t);
};

/** Listbox row content for a create option (icon + call-to-action text). */
export function CreateOptionRow({text}: {text: string}) {
    return (
        <Stack direction="row" alignItems="center" gap={0.5} sx={{color: 'primary.main'}}>
            <AddIcon fontSize="small"/>
            <span>{text}</span>
        </Stack>
    );
}
