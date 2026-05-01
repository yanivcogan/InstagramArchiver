import React, {useEffect, useMemo, useRef, useState} from 'react';
import {Box, Button, Chip, Menu, MenuItem, MenuList, Paper, Popper} from "@mui/material";
import CheckIcon from '@mui/icons-material/Check';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import ArrowRightIcon from '@mui/icons-material/ArrowRight';
import {IQuickAccessTypeDropdown, ITagWithType} from "../../types/tags";

interface INestedTagMenuItemProps {
    tag: ITagWithType;
    childMap: Map<number, number[]>;
    tagById: Map<number, ITagWithType>;
    assignedTagIds: Set<number>;
    onSelect: (tag: ITagWithType) => void;
    closeRoot: () => void;
    depth?: number;
}

function NestedTagMenuItem({tag, childMap, tagById, assignedTagIds, onSelect, closeRoot, depth = 0}: INestedTagMenuItemProps) {
    const [subAnchor, setSubAnchor] = useState<HTMLElement | null>(null);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const childIds = childMap.get(tag.id) ?? [];
    const hasChildren = childIds.length > 0;
    const assigned = assignedTagIds.has(tag.id);

    useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

    const openSub = (el: HTMLElement) => {
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => setSubAnchor(el), 80);
    };

    const closeSub = () => {
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => setSubAnchor(null), 80);
    };

    const cancelClose = () => {
        if (timerRef.current) clearTimeout(timerRef.current);
    };

    return (
        <>
            <MenuItem
                onMouseEnter={hasChildren ? (e) => openSub(e.currentTarget) : undefined}
                onMouseLeave={hasChildren ? closeSub : undefined}
                onClick={(e) => {
                    e.stopPropagation();
                    onSelect(tag);
                    closeRoot();
                }}
                sx={{gap: 1, justifyContent: 'space-between', pr: hasChildren ? 0.5 : 2}}
            >
                <span style={{display: 'flex', alignItems: 'center', gap: 8}}>
                    <CheckIcon
                        fontSize="small"
                        sx={{visibility: assigned ? 'visible' : 'hidden', color: 'success.main'}}
                    />
                    {tag.name}
                </span>
                {hasChildren && <ArrowRightIcon fontSize="small" sx={{ml: 1, color: 'text.secondary'}}/>}
            </MenuItem>
            {hasChildren && (
                <Popper
                    open={Boolean(subAnchor)}
                    anchorEl={subAnchor}
                    placement="right-start"
                    sx={{zIndex: 1300 + depth + 1}}
                >
                    <Paper
                        elevation={8}
                        onMouseEnter={cancelClose}
                        onMouseLeave={closeSub}
                    >
                        <MenuList>
                            {childIds.map(childId => {
                                const child = tagById.get(childId);
                                if (!child) return null;
                                return (
                                    <NestedTagMenuItem
                                        key={childId}
                                        tag={child}
                                        childMap={childMap}
                                        tagById={tagById}
                                        assignedTagIds={assignedTagIds}
                                        onSelect={onSelect}
                                        closeRoot={closeRoot}
                                        depth={depth + 1}
                                    />
                                );
                            })}
                        </MenuList>
                    </Paper>
                </Popper>
            )}
        </>
    );
}

interface IProps {
    dropdown: IQuickAccessTypeDropdown;
    assignedTagIds: Set<number>;
    onSelect: (tag: ITagWithType) => void;
    placeholder?: string;
}

export default function QuickAccessTypeDropdown({dropdown, assignedTagIds, onSelect, placeholder}: IProps) {
    const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
    const [minWidth, setMinWidth] = useState(0);
    const measureRef = useRef<HTMLSpanElement>(null);

    useEffect(() => {
        if (measureRef.current) {
            setMinWidth(measureRef.current.offsetWidth + 42);
        }
    }, [dropdown.type_name, placeholder]);

    const {childMap, tagById, roots} = useMemo(() => {
        const childMap = new Map<number, number[]>();
        const childSet = new Set<number>();
        for (const edge of (dropdown.hierarchy ?? [])) {
            if (!childMap.has(edge.super_tag_id)) childMap.set(edge.super_tag_id, []);
            childMap.get(edge.super_tag_id)!.push(edge.sub_tag_id);
            childSet.add(edge.sub_tag_id);
        }
        const tagById = new Map(dropdown.tags.map(t => [t.id, t]));
        const roots = dropdown.tags.filter(t => !childSet.has(t.id));
        return {childMap, tagById, roots};
    }, [dropdown.hierarchy, dropdown.tags]);

    const selectedTags = useMemo(
        () => dropdown.tags.filter(t => assignedTagIds.has(t.id)),
        [dropdown.tags, assignedTagIds],
    );

    const closeRoot = () => setAnchorEl(null);

    return (
        <>
            <span
                ref={measureRef}
                style={{
                    position: 'fixed',
                    visibility: 'hidden',
                    pointerEvents: 'none',
                    whiteSpace: 'nowrap',
                    fontSize: '0.8125rem',
                    textTransform: 'uppercase',
                }}
            >
                {placeholder ?? dropdown.type_name}
            </span>
            <Button
                variant="outlined"
                onClick={(e) => setAnchorEl(e.currentTarget)}
                endIcon={<ArrowDropDownIcon/>}
                sx={{
                    minWidth,
                    textTransform: 'uppercase',
                    fontSize: '0.8125rem',
                    fontWeight: 400,
                    paddingTop: '5px',
                    paddingBottom: '5px',
                    paddingLeft: '10px',
                    paddingRight: '6px',
                    color: 'text.primary',
                    borderColor: 'divider',
                    '&:hover': {borderColor: 'text.primary'},
                    '& .MuiButton-endIcon': {marginLeft: 'auto'},
                }}
            >
                {selectedTags.length > 0
                    ? (
                        <Box sx={{display: 'flex', gap: 0.5, flexWrap: 'wrap', alignItems: 'center'}}>
                            {selectedTags.map(tag => (
                                <Chip key={tag.id} label={tag.name} size="small" variant="outlined" color="primary"/>
                            ))}
                        </Box>
                    )
                    : (placeholder ?? dropdown.type_name)
                }
            </Button>
            <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={closeRoot}
                disableAutoFocusItem
            >
                {roots.map(tag => (
                    <NestedTagMenuItem
                        key={tag.id}
                        tag={tag}
                        childMap={childMap}
                        tagById={tagById}
                        assignedTagIds={assignedTagIds}
                        onSelect={onSelect}
                        closeRoot={closeRoot}
                    />
                ))}
            </Menu>
        </>
    );
}
