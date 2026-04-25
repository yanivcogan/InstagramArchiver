import React, {useRef, useState} from 'react';
import {
    Alert,
    Box,
    Button,
    Checkbox,
    Chip,
    CircularProgress,
    FormControlLabel,
    Stack,
    Step,
    StepLabel,
    Stepper,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import {toast} from 'material-react-toastify';
import {ITagImportExecuteResponse, ITagImportRowInput, ITagImportRowParsed,} from '../../types/tags';
import {executeTagImport, previewTagImport} from '../../services/TagManagementService';
import {downloadTextFile} from '../../services/utils';

const STEPS = ['Upload File', 'Preview & Edit', 'Results'];

const TEMPLATE_CSV =
    'name,tag_type,description,quick_access,parents\n' +
    'Example Tag,My Type,A description,false,Parent Tag 1|Parent Tag 2\n' +
    'Parent Tag 1,My Type,,false,\n' +
    'Parent Tag 2,My Type,,false,\n';

function downloadTemplate() {
    downloadTextFile(TEMPLATE_CSV, 'tag_import_template.csv', 'text/csv');
}

/* ── Step 0: Upload ──────────────────────────────────────────────────────────── */

function UploadStep({onParsed}: {onParsed: (rows: ITagImportRowParsed[]) => void}) {
    const [loading, setLoading] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    const handleFile = async (file: File) => {
        setLoading(true);
        try {
            const parsed = await previewTagImport(file);
            onParsed(parsed);
        } catch (e: any) {
            toast.error(e?.message || 'Failed to parse file');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Stack gap={3} alignItems="flex-start" sx={{maxWidth: 520}}>
            <Typography variant="body2" color="text.secondary">
                Upload a CSV or XLSX file to import tags and hierarchy relationships in bulk.
                The file must have a <strong>name</strong> column. Optional columns:
                {' '}<code>tag_type</code>, <code>description</code>, <code>quick_access</code>,
                {' '}<code>parents</code> (pipe-separated parent tag names).
            </Typography>
            <Stack direction="row" gap={2}>
                <Button variant="outlined" startIcon={<DownloadIcon/>} onClick={downloadTemplate}>
                    Download template
                </Button>
                <Button
                    variant="contained"
                    startIcon={loading ? <CircularProgress size={16} color="inherit"/> : <UploadFileIcon/>}
                    disabled={loading}
                    onClick={() => inputRef.current?.click()}
                >
                    Select file
                </Button>
            </Stack>
            <input
                ref={inputRef}
                type="file"
                accept=".csv,.xlsx"
                style={{display: 'none'}}
                onChange={e => {
                    const file = e.target.files?.[0];
                    if (file) handleFile(file);
                    e.target.value = '';
                }}
            />
        </Stack>
    );
}

/* ── Step 1: Preview & Edit ─────────────────────────────────────────────────── */

type RowUpdate = Partial<ITagImportRowInput>;

function PreviewStep({
    rows,
    createMissingTypes,
    onCreateMissingTypesChange,
    onUpdateRow,
    onImport,
    loading,
}: {
    rows: ITagImportRowInput[];
    createMissingTypes: boolean;
    onCreateMissingTypesChange: (v: boolean) => void;
    onUpdateRow: (index: number, update: RowUpdate) => void;
    onImport: () => void;
    loading: boolean;
}) {
    return (
        <Stack gap={2}>
            <Typography variant="body2" color="text.secondary">
                Review and edit the rows below before importing. The <em>parents</em> column uses
                pipe (<code>|</code>) to separate multiple parent tag names.
            </Typography>
            <Box sx={{overflowX: 'auto'}}>
                <Table size="small" sx={{'& td, & th': {py: 0.5}}}>
                    <TableHead>
                        <TableRow>
                            <TableCell sx={{width: 36}}>#</TableCell>
                            <TableCell>Name *</TableCell>
                            <TableCell>Tag Type</TableCell>
                            <TableCell>Description</TableCell>
                            <TableCell sx={{width: 110}}>Quick Access</TableCell>
                            <TableCell>Parents (pipe-separated)</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {rows.map((row, i) => (
                            <TableRow key={i}>
                                <TableCell sx={{color: 'text.secondary', fontSize: '0.75rem'}}>{i + 1}</TableCell>
                                <TableCell>
                                    <TextField
                                        size="small"
                                        value={row.name}
                                        onChange={e => onUpdateRow(i, {name: e.target.value})}
                                        error={row.name.includes(',')}
                                        helperText={row.name.includes(',') ? 'No commas allowed' : undefined}
                                        sx={{minWidth: 140}}
                                    />
                                </TableCell>
                                <TableCell>
                                    <TextField
                                        size="small"
                                        value={row.tag_type ?? ''}
                                        onChange={e => onUpdateRow(i, {tag_type: e.target.value || null})}
                                        sx={{minWidth: 120}}
                                    />
                                </TableCell>
                                <TableCell>
                                    <TextField
                                        size="small"
                                        value={row.description ?? ''}
                                        onChange={e => onUpdateRow(i, {description: e.target.value || null})}
                                        sx={{minWidth: 160}}
                                    />
                                </TableCell>
                                <TableCell padding="checkbox">
                                    <Checkbox
                                        checked={row.quick_access}
                                        onChange={e => onUpdateRow(i, {quick_access: e.target.checked})}
                                        size="small"
                                    />
                                </TableCell>
                                <TableCell>
                                    <TextField
                                        size="small"
                                        value={row.parents.join('|')}
                                        onChange={e => onUpdateRow(i, {
                                            parents: e.target.value.split('|').map(s => s.trim()).filter(Boolean)
                                        })}
                                        sx={{minWidth: 200}}
                                        placeholder="Parent1|Parent2"
                                    />
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </Box>
            <Stack direction="row" gap={2} alignItems="center" flexWrap="wrap">
                <FormControlLabel
                    control={
                        <Checkbox
                            checked={createMissingTypes}
                            onChange={e => onCreateMissingTypesChange(e.target.checked)}
                            size="small"
                        />
                    }
                    label="Create missing tag types automatically"
                />
                <Button
                    variant="contained"
                    onClick={onImport}
                    disabled={loading || rows.some(r => r.name.includes(','))}
                    startIcon={loading ? <CircularProgress size={16} color="inherit"/> : undefined}
                >
                    Import {rows.length} rows
                </Button>
            </Stack>
        </Stack>
    );
}

/* ── Step 2: Results ─────────────────────────────────────────────────────────── */

const STATUS_COLORS: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
    created: 'success',
    existing: 'default',
    error: 'error',
};

const REL_STATUS_COLORS: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
    added: 'success',
    exists: 'default',
    cycle: 'warning',
    parent_not_found: 'error',
};

function ResultsStep({
    response,
    originalRows,
    onRetryFailed,
}: {
    response: ITagImportExecuteResponse;
    originalRows: ITagImportRowInput[];
    onRetryFailed: (failedRows: ITagImportRowInput[]) => void;
}) {
    const {results, summary} = response;
    const errorResults = results.filter(r => r.status === 'error');

    return (
        <Stack gap={2}>
            <Stack direction="row" gap={1} flexWrap="wrap">
                {summary.created > 0 && <Chip label={`${summary.created} created`} color="success" size="small"/>}
                {summary.existing > 0 && <Chip label={`${summary.existing} already existed`} color="default" size="small"/>}
                {summary.errors > 0 && <Chip label={`${summary.errors} errors`} color="error" size="small"/>}
                {summary.relationships_added > 0 && <Chip label={`${summary.relationships_added} relationships added`} color="info" size="small"/>}
                {summary.cycles_skipped > 0 && <Chip label={`${summary.cycles_skipped} cycles skipped`} color="warning" size="small"/>}
            </Stack>

            {errorResults.length > 0 && (
                <Alert
                    severity="error"
                    action={
                        <Button
                            size="small"
                            color="inherit"
                            onClick={() => {
                                const failedRows = errorResults.map(r => ({
                                    ...(originalRows[r.row_index] ?? {
                                        name: r.tag_name,
                                        tag_type: null,
                                        description: null,
                                        quick_access: false,
                                        parents: [],
                                    }),
                                }));
                                onRetryFailed(failedRows);
                            }}
                        >
                            Edit &amp; Retry
                        </Button>
                    }
                >
                    {errorResults.length} row(s) failed. Click "Edit &amp; Retry" to fix and resubmit them.
                </Alert>
            )}

            <Box sx={{overflowX: 'auto'}}>
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell sx={{width: 36}}>#</TableCell>
                            <TableCell>Tag Name</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell>Errors</TableCell>
                            <TableCell>Relationships</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {results.map(r => (
                            <TableRow
                                key={r.row_index}
                                sx={r.status === 'error' ? {backgroundColor: '#fff5f5'} : undefined}
                            >
                                <TableCell sx={{color: 'text.secondary', fontSize: '0.75rem'}}>{r.row_index + 1}</TableCell>
                                <TableCell>{r.tag_name}</TableCell>
                                <TableCell>
                                    <Chip label={r.status} color={STATUS_COLORS[r.status] ?? 'default'} size="small"/>
                                </TableCell>
                                <TableCell>
                                    <Stack gap={0.25}>
                                        {r.errors.map((e, i) => (
                                            <Typography key={i} variant="caption" color="error">{e}</Typography>
                                        ))}
                                    </Stack>
                                </TableCell>
                                <TableCell>
                                    <Stack direction="row" gap={0.5} flexWrap="wrap">
                                        {r.relationships.map((rel, i) => (
                                            <Tooltip key={i} title={`Parent: ${rel.parent_name} — ${rel.status}`} disableInteractive>
                                                <Chip
                                                    label={rel.parent_name}
                                                    color={REL_STATUS_COLORS[rel.status] ?? 'default'}
                                                    size="small"
                                                    variant="outlined"
                                                />
                                            </Tooltip>
                                        ))}
                                    </Stack>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </Box>
        </Stack>
    );
}

/* ── Main component ──────────────────────────────────────────────────────────── */

export default function ImportTagsTab() {
    const [step, setStep] = useState(0);
    const [editableRows, setEditableRows] = useState<ITagImportRowInput[]>([]);
    const [createMissingTypes, setCreateMissingTypes] = useState(false);
    const [importResult, setImportResult] = useState<ITagImportExecuteResponse | null>(null);
    const [importing, setImporting] = useState(false);

    const handleParsed = (parsed: ITagImportRowParsed[]) => {
        setEditableRows(parsed.map(p => ({
            name: p.name,
            tag_type: p.tag_type,
            description: p.description,
            quick_access: p.quick_access,
            parents: [...p.parents],
        })));
        setStep(1);
    };

    const handleUpdateRow = (index: number, update: RowUpdate) => {
        setEditableRows(prev => prev.map((r, i) => i === index ? {...r, ...update} : r));
    };

    const handleImport = async () => {
        setImporting(true);
        try {
            const result = await executeTagImport(editableRows, createMissingTypes);
            setImportResult(result);
            setStep(2);
        } catch (e: any) {
            toast.error(e?.message || 'Import failed');
        } finally {
            setImporting(false);
        }
    };

    const handleRetryFailed = (failedRows: ITagImportRowInput[]) => {
        setEditableRows(failedRows);
        setImportResult(null);
        setStep(1);
    };

    return (
        <Stack gap={3}>
            <Stepper activeStep={step} sx={{maxWidth: 600}}>
                {STEPS.map(label => (
                    <Step key={label}><StepLabel>{label}</StepLabel></Step>
                ))}
            </Stepper>

            {step === 0 && <UploadStep onParsed={handleParsed}/>}

            {step === 1 && (
                <PreviewStep
                    rows={editableRows}
                    createMissingTypes={createMissingTypes}
                    onCreateMissingTypesChange={setCreateMissingTypes}
                    onUpdateRow={handleUpdateRow}
                    onImport={handleImport}
                    loading={importing}
                />
            )}

            {step === 2 && importResult && (
                <ResultsStep
                    response={importResult}
                    originalRows={editableRows}
                    onRetryFailed={handleRetryFailed}
                />
            )}

            {step > 0 && (
                <Box>
                    <Button size="small" onClick={() => { setStep(0); setImportResult(null); setEditableRows([]); }}>
                        ← Start over
                    </Button>
                </Box>
            )}
        </Stack>
    );
}
