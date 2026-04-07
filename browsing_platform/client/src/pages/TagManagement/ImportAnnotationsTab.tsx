import React, {useRef, useState} from 'react';
import {
    Alert,
    Box,
    Button,
    ButtonGroup,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    MenuItem,
    Select,
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
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import ContentPasteIcon from '@mui/icons-material/ContentPaste';
import DownloadIcon from '@mui/icons-material/Download';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import RefreshIcon from '@mui/icons-material/Refresh';
import {toast} from 'material-react-toastify';
import {
    IAnnotationImportExecuteResponse,
    IAnnotationImportRowInput,
    IResolvedAnnotationRow,
    ITagWithType,
} from '../../types/tags';
import {executeAnnotationImport, previewAnnotationImport} from '../../services/TagManagementService';
import TagSelector from '../../UIComponents/Tags/TagSelector';

const STEPS = ['Upload File', 'Preview & Edit', 'Results'];
const ENTITY_TYPES = ['account', 'post', 'media', 'media_part'];

const TEMPLATE_CSV =
    'entity_type,entity,tag,tag_type,notes\n' +
    'account,@username,Example Tag,My Type,\n' +
    'account,123,Another Tag,,some note\n' +
    'post,456,Example Tag,,\n';

function downloadTemplate() {
    const blob = new Blob([TEMPLATE_CSV], {type: 'text/csv'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'annotation_import_template.csv';
    a.click();
    URL.revokeObjectURL(url);
}

function rowsToCSV(rows: IAnnotationImportRowInput[]): File {
    const header = 'entity_type,entity,tag,tag_type,notes\n';
    const body = rows.map(r =>
        [r.entity_type, r.entity, r.tag, r.tag_type ?? '', r.notes ?? '']
            .map(v => `"${String(v).replace(/"/g, '""')}"`)
            .join(',')
    ).join('\n');
    const blob = new Blob([header + body], {type: 'text/csv'});
    return new File([blob], 'rows.csv', {type: 'text/csv'});
}

/* ── Prompt generation ───────────────────────────────────────────────────────── */

function buildPrompt(tags: ITagWithType[]): string {
    // Group tags by type for readability
    const byType: Record<string, ITagWithType[]> = {};
    for (const tag of tags) {
        const key = tag.tag_type_name ?? '(no type)';
        (byType[key] ??= []).push(tag);
    }

    const tagLines: string[] = [];
    for (const [typeName, typeTags] of Object.entries(byType)) {
        if (typeName !== '(no type)') {
            tagLines.push(`  [${typeName}]`);
        }
        for (const tag of typeTags) {
            const typeClause = tag.tag_type_name ? ` [type: ${tag.tag_type_name}]` : '';
            const descClause = tag.description ? ` — ${tag.description}` : '';
            tagLines.push(`  - ${tag.name}${typeClause}${descClause}`);
        }
    }

    return `\
You are a data formatting assistant. Your task is to convert the attached input file \
into a properly structured CSV for bulk annotation import into an archiving system.

## Output Format
Produce a CSV file with exactly these columns (header row required):
entity_type,entity,tag,tag_type,notes

### Column rules

**entity_type** — must be exactly one of: account, post, media, media_part

**entity** — the entity identifier:
  For \`account\`:
    Use the username (URL suffix) ONLY.
    ✓ Correct:   johndoe
    ✓ Correct:   @johndoe
    ✗ Incorrect: https://www.instagram.com/johndoe
    ✗ Incorrect: https://instagram.com/johndoe/
    ✗ Incorrect: www.instagram.com/johndoe
    If the input contains a full URL, extract only the username portion \
(the last path segment, without slashes or query strings).
  For \`post\`, \`media\`, \`media_part\`:
    Use the internal numeric ID only (not a URL, shortcode, or any other identifier).

**tag** — use the exact canonical tag name from the Available Tags list below \
(matching is case-insensitive, but use the canonical capitalisation when possible).

**tag_type** — include the tag's type as listed below. This is required when a tag \
name could be ambiguous; include it for all tags where a type is listed.

**notes** — optional free-text explaining why this tag was assigned. Leave empty \
if not applicable.

## Available Tags
${tagLines.join('\n')}

## Example Output
entity_type,entity,tag,tag_type,notes
account,johndoe,Politician,US Politics,confirmed via bio
account,@janedoe,Activist,,
post,12345,Video Content,Content Type,

## Rules
1. Only use tags from the Available Tags list above. If no tag clearly matches an \
intended annotation, skip that row entirely.
2. For accounts, always extract just the username from any URL form.
3. For posts, media, and media_parts, only include rows where you have a numeric ID.
4. Output the CSV content only — no prose, no explanation, no markdown fences.
5. Include the header row exactly as shown above.`;
}

function PromptGeneratorDialog({open, onClose}: {open: boolean; onClose: () => void}) {
    const [selectedTags, setSelectedTags] = useState<ITagWithType[]>([]);
    const [generatedPrompt, setGeneratedPrompt] = useState<string | null>(null);

    const handleGenerate = () => {
        setGeneratedPrompt(buildPrompt(selectedTags));
    };

    const handleCopy = () => {
        if (generatedPrompt) {
            navigator.clipboard.writeText(generatedPrompt);
            toast.success('Prompt copied to clipboard!');
        }
    };

    const handleClose = () => {
        onClose();
        // Reset state so next open is fresh
        setSelectedTags([]);
        setGeneratedPrompt(null);
    };

    return (
        <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
            <DialogTitle>Generate LLM Prompt</DialogTitle>
            <DialogContent>
                <Stack gap={2} sx={{mt: 0.5}}>
                    <Typography variant="body2" color="text.secondary">
                        Select the tags you plan to assign. The generated prompt can be pasted into
                        any LLM alongside your source file — the LLM will reformat it into the CSV
                        structure this import tool expects.
                    </Typography>
                    <TagSelector
                        selectedTags={selectedTags}
                        onChange={tags => {
                            setSelectedTags(tags);
                            setGeneratedPrompt(null); // invalidate on change
                        }}
                        label="Working tags"
                    />
                    <Box>
                        <Button
                            variant="outlined"
                            startIcon={<AutoAwesomeIcon/>}
                            onClick={handleGenerate}
                            disabled={selectedTags.length === 0}
                        >
                            Generate prompt
                        </Button>
                    </Box>
                    {generatedPrompt !== null && (
                        <Stack gap={1}>
                            <TextField
                                value={generatedPrompt}
                                multiline
                                rows={16}
                                fullWidth
                                InputProps={{readOnly: true, sx: {fontFamily: 'monospace', fontSize: '0.8rem'}}}
                            />
                            <Box>
                                <Button
                                    variant="contained"
                                    startIcon={<ContentCopyIcon/>}
                                    onClick={handleCopy}
                                >
                                    Copy to clipboard
                                </Button>
                            </Box>
                        </Stack>
                    )}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
}

/* ── Step 0: Upload ──────────────────────────────────────────────────────────── */

function UploadStep({onResolved}: {onResolved: (rows: IResolvedAnnotationRow[]) => void}) {
    const [loading, setLoading] = useState(false);
    const [promptDialogOpen, setPromptDialogOpen] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    const handleFile = async (file: File) => {
        setLoading(true);
        try {
            const resolved = await previewAnnotationImport(file);
            onResolved(resolved);
        } catch (e: any) {
            toast.error(e?.message || 'Failed to parse file');
        } finally {
            setLoading(false);
        }
    };

    const handlePasteFromClipboard = async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (!text.trim()) {
                toast.error('Clipboard is empty');
                return;
            }
            const file = new File([text], 'paste.csv', {type: 'text/csv'});
            await handleFile(file);
        } catch {
            toast.error('Could not read clipboard. Make sure you have granted clipboard permission.');
        }
    };

    return (
        <Stack gap={3} alignItems="flex-start" sx={{maxWidth: 560}}>
            <Typography variant="body2" color="text.secondary">
                Upload a CSV or XLSX file to assign tags to entities in bulk.
                Required columns: <strong>entity_type</strong>, <strong>entity</strong>, <strong>tag</strong>.
                Optional: <code>tag_type</code> (to disambiguate), <code>notes</code>.
                For accounts, <code>entity</code> can be a URL suffix (<code>@username</code>) or numeric ID.
            </Typography>

            <Stack gap={1.5} alignItems="flex-start">
                <Typography variant="caption" color="text.secondary">Prepare your file</Typography>
                <ButtonGroup variant="outlined">
                    <Button startIcon={<DownloadIcon/>} onClick={downloadTemplate}>
                        Download template
                    </Button>
                    <Button startIcon={<AutoAwesomeIcon/>} onClick={() => setPromptDialogOpen(true)}>
                        Generate LLM Prompt
                    </Button>
                </ButtonGroup>
            </Stack>

            <Stack gap={1.5} alignItems="flex-start">
                <Typography variant="caption" color="text.secondary">Load your file</Typography>
                <Stack direction="row" gap={2}>
                    <Button
                        variant="contained"
                        startIcon={loading ? <CircularProgress size={16} color="inherit"/> : <UploadFileIcon/>}
                        disabled={loading}
                        onClick={() => inputRef.current?.click()}
                    >
                        Select file
                    </Button>
                    <Button
                        variant="outlined"
                        startIcon={loading ? <CircularProgress size={16}/> : <ContentPasteIcon/>}
                        disabled={loading}
                        onClick={handlePasteFromClipboard}
                    >
                        Paste from clipboard
                    </Button>
                </Stack>
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

            <PromptGeneratorDialog
                open={promptDialogOpen}
                onClose={() => setPromptDialogOpen(false)}
            />
        </Stack>
    );
}

/* ── Step 1: Preview & Edit ─────────────────────────────────────────────────── */

type RowUpdate = Partial<IAnnotationImportRowInput>;

function PreviewStep({
    rows,
    resolved,
    onUpdateRow,
    onRepreview,
    onImport,
    repreviewing,
    importing,
}: {
    rows: IAnnotationImportRowInput[];
    resolved: IResolvedAnnotationRow[];
    onUpdateRow: (index: number, update: RowUpdate) => void;
    onRepreview: () => void;
    onImport: () => void;
    repreviewing: boolean;
    importing: boolean;
}) {
    const errorCount = resolved.filter(r => r.parse_errors.length > 0).length;

    return (
        <Stack gap={2}>
            <Typography variant="body2" color="text.secondary">
                Review and correct the rows below. The "Resolved" column shows the detected entity.
                After editing, click <strong>Re-resolve</strong> to refresh entity/tag lookups, then <strong>Import</strong>.
            </Typography>
            {errorCount > 0 && (
                <Alert severity="warning">{errorCount} row(s) have unresolved errors. Fix them below and re-resolve before importing.</Alert>
            )}
            <Box sx={{overflowX: 'auto'}}>
                <Table size="small" sx={{'& td, & th': {py: 0.5}}}>
                    <TableHead>
                        <TableRow>
                            <TableCell sx={{width: 36}}>#</TableCell>
                            <TableCell>Entity Type</TableCell>
                            <TableCell>Entity (ID or @username)</TableCell>
                            <TableCell>Resolved</TableCell>
                            <TableCell>Tag</TableCell>
                            <TableCell>Tag Type</TableCell>
                            <TableCell>Notes</TableCell>
                            <TableCell>Errors</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {rows.map((row, i) => {
                            const res = resolved[i];
                            const hasError = res?.parse_errors?.length > 0;
                            return (
                                <TableRow
                                    key={i}
                                    sx={hasError ? {backgroundColor: '#fff5f5'} : undefined}
                                >
                                    <TableCell sx={{color: 'text.secondary', fontSize: '0.75rem'}}>{i + 1}</TableCell>
                                    <TableCell>
                                        <Select
                                            size="small"
                                            value={row.entity_type}
                                            onChange={e => onUpdateRow(i, {entity_type: e.target.value})}
                                            sx={{minWidth: 100}}
                                        >
                                            {ENTITY_TYPES.map(t => <MenuItem key={t} value={t}>{t}</MenuItem>)}
                                        </Select>
                                    </TableCell>
                                    <TableCell>
                                        <TextField
                                            size="small"
                                            value={row.entity}
                                            onChange={e => onUpdateRow(i, {entity: e.target.value})}
                                            sx={{minWidth: 140}}
                                            placeholder="123 or @username"
                                        />
                                    </TableCell>
                                    <TableCell>
                                        {res?.entity_id != null ? (
                                            <Tooltip title={`ID: ${res.entity_id}`} disableInteractive>
                                                <Chip
                                                    label={res.entity_display ?? String(res.entity_id)}
                                                    size="small"
                                                    color="success"
                                                    variant="outlined"
                                                />
                                            </Tooltip>
                                        ) : (
                                            <Typography variant="caption" color="text.disabled">—</Typography>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <TextField
                                            size="small"
                                            value={row.tag}
                                            onChange={e => onUpdateRow(i, {tag: e.target.value})}
                                            sx={{minWidth: 140}}
                                        />
                                    </TableCell>
                                    <TableCell>
                                        <TextField
                                            size="small"
                                            value={row.tag_type ?? ''}
                                            onChange={e => onUpdateRow(i, {tag_type: e.target.value || null})}
                                            sx={{minWidth: 120}}
                                            placeholder="(optional)"
                                        />
                                    </TableCell>
                                    <TableCell>
                                        <TextField
                                            size="small"
                                            value={row.notes ?? ''}
                                            onChange={e => onUpdateRow(i, {notes: e.target.value || null})}
                                            sx={{minWidth: 160}}
                                        />
                                    </TableCell>
                                    <TableCell>
                                        <Stack gap={0.25}>
                                            {(res?.parse_errors ?? []).map((e, j) => (
                                                <Typography key={j} variant="caption" color="error">{e}</Typography>
                                            ))}
                                        </Stack>
                                    </TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </Box>
            <Stack direction="row" gap={2} alignItems="center" flexWrap="wrap">
                <Button
                    variant="outlined"
                    startIcon={repreviewing ? <CircularProgress size={16}/> : <RefreshIcon/>}
                    onClick={onRepreview}
                    disabled={repreviewing || importing}
                >
                    Re-resolve
                </Button>
                <Button
                    variant="contained"
                    onClick={onImport}
                    disabled={importing || repreviewing || errorCount > 0}
                    startIcon={importing ? <CircularProgress size={16} color="inherit"/> : undefined}
                >
                    Import {rows.length} rows
                </Button>
            </Stack>
        </Stack>
    );
}

/* ── Step 2: Results ─────────────────────────────────────────────────────────── */

const STATUS_COLORS: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
    added: 'success',
    exists: 'default',
    error: 'error',
};

function ResultsStep({
    response,
    originalRows,
    onRetryFailed,
}: {
    response: IAnnotationImportExecuteResponse;
    originalRows: IAnnotationImportRowInput[];
    onRetryFailed: (rows: IAnnotationImportRowInput[]) => void;
}) {
    const {results, summary} = response;
    const errorResults = results.filter(r => r.status === 'error');

    return (
        <Stack gap={2}>
            <Stack direction="row" gap={1} flexWrap="wrap">
                {summary.added > 0 && <Chip label={`${summary.added} added`} color="success" size="small"/>}
                {summary.exists > 0 && <Chip label={`${summary.exists} already existed`} color="default" size="small"/>}
                {summary.errors > 0 && <Chip label={`${summary.errors} errors`} color="error" size="small"/>}
            </Stack>

            {errorResults.length > 0 && (
                <Alert
                    severity="error"
                    action={
                        <Button
                            size="small"
                            color="inherit"
                            onClick={() => {
                                const failed = errorResults.map(r => ({...originalRows[r.row_index]}));
                                onRetryFailed(failed);
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
                            <TableCell>Entity</TableCell>
                            <TableCell>Tag</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell>Errors</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {results.map(r => {
                            const orig = originalRows[r.row_index];
                            return (
                                <TableRow
                                    key={r.row_index}
                                    sx={r.status === 'error' ? {backgroundColor: '#fff5f5'} : undefined}
                                >
                                    <TableCell sx={{color: 'text.secondary', fontSize: '0.75rem'}}>{r.row_index + 1}</TableCell>
                                    <TableCell>
                                        <Typography variant="caption">{orig?.entity_type}: {orig?.entity}</Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant="caption">{orig?.tag}</Typography>
                                    </TableCell>
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
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </Box>
        </Stack>
    );
}

/* ── Main component ──────────────────────────────────────────────────────────── */

export default function ImportAnnotationsTab() {
    const [step, setStep] = useState(0);
    const [editableRows, setEditableRows] = useState<IAnnotationImportRowInput[]>([]);
    const [resolvedRows, setResolvedRows] = useState<IResolvedAnnotationRow[]>([]);
    const [importResult, setImportResult] = useState<IAnnotationImportExecuteResponse | null>(null);
    const [repreviewing, setRepreviewing] = useState(false);
    const [importing, setImporting] = useState(false);

    const handleResolved = (rows: IResolvedAnnotationRow[]) => {
        setResolvedRows(rows);
        setEditableRows(rows.map(r => ({
            entity_type: r.entity_type,
            entity: r.entity_raw,
            tag: r.tag_name,
            tag_type: r.tag_type,
            notes: r.notes,
        })));
        setStep(1);
    };

    const handleUpdateRow = (index: number, update: RowUpdate) => {
        setEditableRows(prev => prev.map((r, i) => i === index ? {...r, ...update} : r));
    };

    const handleRepreview = async () => {
        setRepreviewing(true);
        try {
            const file = rowsToCSV(editableRows);
            const resolved = await previewAnnotationImport(file);
            setResolvedRows(resolved);
        } catch (e: any) {
            toast.error(e?.message || 'Re-resolve failed');
        } finally {
            setRepreviewing(false);
        }
    };

    const handleImport = async () => {
        setImporting(true);
        try {
            const result = await executeAnnotationImport(editableRows);
            setImportResult(result);
            setStep(2);
        } catch (e: any) {
            toast.error(e?.message || 'Import failed');
        } finally {
            setImporting(false);
        }
    };

    const handleRetryFailed = async (failedRows: IAnnotationImportRowInput[]) => {
        setEditableRows(failedRows);
        setImportResult(null);
        // Re-resolve the failed rows immediately
        setRepreviewing(true);
        try {
            const file = rowsToCSV(failedRows);
            const resolved = await previewAnnotationImport(file);
            setResolvedRows(resolved);
        } catch {
            setResolvedRows(failedRows.map((r, i) => ({
                row_index: i, entity_type: r.entity_type, entity_raw: r.entity,
                entity_id: null, entity_display: null, tag_name: r.tag,
                tag_type: r.tag_type, tag_id: null, notes: r.notes, parse_errors: [],
            })));
        } finally {
            setRepreviewing(false);
        }
        setStep(1);
    };

    return (
        <Stack gap={3}>
            <Stepper activeStep={step} sx={{maxWidth: 600}}>
                {STEPS.map(label => (
                    <Step key={label}><StepLabel>{label}</StepLabel></Step>
                ))}
            </Stepper>

            {step === 0 && <UploadStep onResolved={handleResolved}/>}

            {step === 1 && (
                <PreviewStep
                    rows={editableRows}
                    resolved={resolvedRows}
                    onUpdateRow={handleUpdateRow}
                    onRepreview={handleRepreview}
                    onImport={handleImport}
                    repreviewing={repreviewing}
                    importing={importing}
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
                    <Button size="small" onClick={() => { setStep(0); setImportResult(null); setEditableRows([]); setResolvedRows([]); }}>
                        ← Start over
                    </Button>
                </Box>
            )}
        </Stack>
    );
}
