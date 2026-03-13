import React, {useState} from 'react';
import {Chip, ChipTypeMap, Stack, StackTypeMap, Tooltip} from '@mui/material';
import './selfContainedModal.scss';
import {DefaultComponentProps} from "@mui/material/OverridableComponent";

interface IProps {
    chipContents: string[],
    chipsVisibleWhenCollapsed: number,
    expandedByDefault?: boolean,
    stackProps: DefaultComponentProps<StackTypeMap>
    chipProps?: DefaultComponentProps<ChipTypeMap>
}

export default function SelfContainedTruncatedChipList({chipContents, chipsVisibleWhenCollapsed, expandedByDefault, stackProps, chipProps}: IProps) {
    const [expanded, setExpanded] = useState(!!expandedByDefault);

    const plusN = chipContents.length - chipsVisibleWhenCollapsed;
    const plusLabel = chipContents.length > chipsVisibleWhenCollapsed ? `+${plusN}` : null;

    return (
        <Stack gap={1} direction={"row"} width={"90%"} alignItems={"start"} {...stackProps || {}}>
            {chipContents
                .filter((_, i) => expanded || i < chipsVisibleWhenCollapsed)
                .map((s, i) => (
                    <Chip
                        key={i}
                        label={s}
                        size={"small"}
                        variant={"outlined"}
                        onClick={expanded ? () => setExpanded(false) : undefined}
                        sx={{maxWidth: `calc(100% - ${(plusLabel?.length || 0) * 1.25}em)`}}
                        {...chipProps || {}}
                    />
                ))
            }
            {!expanded && plusLabel ? (
                <Tooltip
                    title={
                        <Stack gap={1} direction={"column"} width={"100%"} alignItems={"start"}>
                            {chipContents
                                .filter((_, i) => i >= chipsVisibleWhenCollapsed)
                                .map((s, i) => (
                                    <Chip key={i} label={s} size={"small"} variant={"outlined"} sx={{backgroundColor: "white"}}/>
                                ))
                            }
                        </Stack>
                    }
                    arrow
                >
                    <Chip
                        label={plusLabel}
                        size={"small"}
                        variant={"outlined"}
                        {...chipProps || {}}
                        onClick={() => setExpanded(true)}
                    />
                </Tooltip>
            ) : null}
        </Stack>
    );
}
