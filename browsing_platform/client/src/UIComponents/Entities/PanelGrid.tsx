import React, {useEffect, useMemo, useRef} from 'react';
import {Box} from "@mui/material";
import {DataGrid, GridColDef, GridRowClassNameParams, GridValidRowModel} from "@mui/x-data-grid";
import {SxProps, Theme} from "@mui/material/styles";

const HIGHLIGHT_CLASS = 'panel-row-highlight';

const PAGE_SIZE = 50;

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
    /** Extra per-row class (combined with the highlight class). */
    getRowClassName?: (params: GridRowClassNameParams) => string;
    sx?: SxProps<Theme>;
}

/**
 * Shared table for the entity panels (comments, likes, relations, interactions).
 * Free-version DataGrid: single-column sorting (click a header), column resizing
 * (drag the header separators) and single-filter column filtering (column menu on
 * columns that opt in via `filterable`) work out of the box; multi-sort and
 * multi-filter are Pro features. All rows are fetched by the API — pagination,
 * sorting and filtering are purely client-side.
 */
export default function EntityPanelGrid({rows, columns, highlightId, getRowClassName, sx}: IProps) {
    // DataGrid requires a unique id per row, but some entities lack a DB id —
    // fall back to a synthetic negative id that can never collide with a real one.
    const gridRows = useMemo(
        () => rows.map((r, i) => ({...r, __rowId: r.id ?? -(i + 1)})),
        [rows]
    );

    // Grid row id of the highlighted entity (its data-id attribute in the DOM).
    const highlightRowId = useMemo(() => {
        if (highlightId == null) return null;
        return gridRows.find(r => r.id === highlightId)?.__rowId ?? null;
    }, [gridRows, highlightId]);

    // Open on the highlighted row's page so deep links work beyond page one.
    // initialState is only read on mount; the panels mount this component with rows present.
    const initialPage = useMemo(() => {
        if (highlightId == null) return 0;
        const idx = gridRows.findIndex(r => r.id === highlightId);
        return idx >= 0 ? Math.floor(idx / PAGE_SIZE) : 0;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const rootRef = useRef<HTMLDivElement>(null);
    const scrolledRef = useRef(false);

    // Scroll the highlighted row into view once it exists in the DOM. DataGrid renders
    // rows only after measuring its container, so poll across a few animation frames.
    useEffect(() => {
        if (highlightRowId == null || scrolledRef.current) return;
        let cancelled = false;
        let attempts = 0;
        const tryScroll = () => {
            if (cancelled) return;
            const el = rootRef.current?.querySelector(`[data-id="${highlightRowId}"]`);
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
    }, [highlightRowId, gridRows]);

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
                hideFooter={rows.length <= PAGE_SIZE}
                pageSizeOptions={[PAGE_SIZE]}
                initialState={{pagination: {paginationModel: {pageSize: PAGE_SIZE, page: initialPage}}}}
                getRowClassName={params => {
                    const classes: string[] = [];
                    if (getRowClassName) classes.push(getRowClassName(params));
                    if (params.row.id != null && params.row.id === highlightId) classes.push(HIGHLIGHT_CLASS);
                    return classes.filter(Boolean).join(' ');
                }}
                sx={[BASE_SX, ...(Array.isArray(sx) ? sx : [sx])] as SxProps<Theme>}
            />
        </Box>
    );
}
