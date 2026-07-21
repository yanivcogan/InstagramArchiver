import React, {useEffect, useMemo, useRef} from 'react';
import {Box} from "@mui/material";
import {DataGrid, GridColDef, GridValidRowModel} from "@mui/x-data-grid";
import {SxProps, Theme} from "@mui/material/styles";

const HIGHLIGHT_CLASS = 'panel-row-highlight';

// The free (MIT) DataGrid caps pages at 100 rows; the footer is only shown when it's needed.
const PAGE_SIZE = 100;

const BASE_SX: SxProps<Theme> = {
    border: 'none',
    fontSize: '0.8125rem',
    '& .MuiDataGrid-columnHeaderTitle': {
        fontSize: '0.75rem',
        fontWeight: 600,
        color: 'text.secondary',
    },
    '& .MuiDataGrid-cell': {
        py: 0.5,
        display: 'flex',
        alignItems: 'flex-start',
        whiteSpace: 'normal',
        overflowWrap: 'anywhere',
    },
    '& .MuiDataGrid-cell:focus, & .MuiDataGrid-cell:focus-within': {
        outline: 'none',
    },
    [`& .${HIGHLIGHT_CLASS}, & .${HIGHLIGHT_CLASS}:hover, & .${HIGHLIGHT_CLASS}.Mui-hovered`]: {
        backgroundColor: '#fff8dc',
    },
};

interface IProps {
    rows: Array<GridValidRowModel & {id?: number}>;
    columns: GridColDef[];
    /** DB id of the row to highlight and scroll into view (deep-link support). */
    highlightId?: number;
    sx?: SxProps<Theme>;
}

/**
 * Shared table for the entity panels (comments, likes, relations, interactions).
 * Free-version DataGrid: single-column sorting (click a header) and column resizing
 * (drag the header separators) work out of the box; multi-sort is a Pro feature.
 */
export default function EntityPanelGrid({rows, columns, highlightId, sx}: IProps) {
    // DataGrid requires a unique id per row, but some entities lack a DB id —
    // fall back to a synthetic negative id that can never collide with a real one.
    const gridRows = useMemo(
        () => rows.map((r, i) => ({...r, __rowId: r.id ?? -(i + 1)})),
        [rows]
    );

    const rootRef = useRef<HTMLDivElement>(null);
    const scrolledRef = useRef(false);

    // Scroll the highlighted row into view once it exists in the DOM. DataGrid renders
    // rows only after measuring its container, so poll across a few animation frames.
    useEffect(() => {
        if (highlightId == null || scrolledRef.current) return;
        let cancelled = false;
        let attempts = 0;
        const tryScroll = () => {
            if (cancelled) return;
            const el = rootRef.current?.querySelector(`[data-id="${highlightId}"]`);
            if (el instanceof HTMLElement) {
                scrolledRef.current = true;
                el.scrollIntoView({behavior: 'smooth', block: 'center'});
            } else if (attempts++ < 30) {
                requestAnimationFrame(tryScroll);
            }
        };
        tryScroll();
        return () => {
            cancelled = true;
        };
    }, [highlightId, gridRows]);

    return (
        <Box ref={rootRef}>
            <DataGrid
                rows={gridRows}
                columns={columns}
                getRowId={r => r.__rowId}
                autoHeight
                density="compact"
                getRowHeight={() => 'auto'}
                disableRowSelectionOnClick
                disableColumnMenu
                hideFooter={rows.length <= PAGE_SIZE}
                pageSizeOptions={[PAGE_SIZE]}
                initialState={{pagination: {paginationModel: {pageSize: PAGE_SIZE}}}}
                getRowClassName={params =>
                    params.row.id != null && params.row.id === highlightId ? HIGHLIGHT_CLASS : ''
                }
                sx={[BASE_SX, ...(Array.isArray(sx) ? sx : [sx])] as SxProps<Theme>}
            />
        </Box>
    );
}
