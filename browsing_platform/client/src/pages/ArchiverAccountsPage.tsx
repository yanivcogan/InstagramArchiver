import React, {useEffect, useRef, useState} from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControl,
    IconButton,
    Input,
    InputLabel,
    LinearProgress,
    Stack,
    Tooltip,
    Typography,
} from "@mui/material";
import {DataGrid, GridColDef} from "@mui/x-data-grid";
import {Delete, Edit, PersonAdd, Upload as UploadIcon} from "@mui/icons-material";
import PageShell from "./PageShell";
import server, {HTTP_METHODS} from "../services/server";
import {
    createArchiverAccount,
    deleteArchiverAccount,
    fetchArchiverAccounts,
    ingestStagedExport,
    renameArchiverAccount,
} from "../services/DataFetcher";
import {formatBytes, uploadFilesViaTus} from "../lib/folderUpload";
import {IArchiverAccountCounts, IArchiverAccountSummary} from "../types/entities";

const RELATION_PATH_MARKER = "connections/followers_and_following/";

type UploadPhase = 'uploading' | 'ingesting' | 'done' | 'error';

export default function ArchiverAccountsPage() {
    const [accounts, setAccounts] = useState<IArchiverAccountSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Add / rename dialogs
    const [addOpen, setAddOpen] = useState(false);
    const [addLabel, setAddLabel] = useState("");
    const [addBusy, setAddBusy] = useState(false);
    const [addError, setAddError] = useState<string | null>(null);

    const [renameTarget, setRenameTarget] = useState<IArchiverAccountSummary | null>(null);
    const [renameLabel, setRenameLabel] = useState("");
    const [renameBusy, setRenameBusy] = useState(false);
    const [renameError, setRenameError] = useState<string | null>(null);

    const [deleteTarget, setDeleteTarget] = useState<IArchiverAccountSummary | null>(null);
    const [deleteBusy, setDeleteBusy] = useState(false);

    // Upload flow
    const fileInputRef = useRef<HTMLInputElement>(null);
    const uploadTargetRef = useRef<IArchiverAccountSummary | null>(null);
    const abortRef = useRef<AbortController | null>(null);
    const stagingNameRef = useRef<string | null>(null);
    const [uploadTarget, setUploadTarget] = useState<IArchiverAccountSummary | null>(null);
    const [uploadPhase, setUploadPhase] = useState<UploadPhase>('uploading');
    const [uploadProgress, setUploadProgress] = useState<{ uploaded: number; total: number; files: number }>({uploaded: 0, total: 0, files: 0});
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [uploadCounts, setUploadCounts] = useState<IArchiverAccountCounts | null>(null);

    useEffect(() => {
        document.title = "Archiver Accounts | Browsing Platform";
        loadAccounts();
    }, []);

    const loadAccounts = async () => {
        setLoading(true);
        try {
            const res = await fetchArchiverAccounts();
            setAccounts(res || []);
            setError(null);
        } catch (e: any) {
            setError(e?.message || "Failed to load archiver accounts");
        } finally {
            setLoading(false);
        }
    };

    const handleAdd = async () => {
        setAddBusy(true);
        setAddError(null);
        try {
            await createArchiverAccount(addLabel.trim());
            setAddOpen(false);
            setAddLabel("");
            loadAccounts();
        } catch (e: any) {
            setAddError(e?.message || "Failed to create archiver account");
        } finally {
            setAddBusy(false);
        }
    };

    const openRename = (row: IArchiverAccountSummary) => {
        setRenameTarget(row);
        setRenameLabel(row.label);
        setRenameError(null);
    };

    const handleRename = async () => {
        if (!renameTarget) return;
        setRenameBusy(true);
        setRenameError(null);
        try {
            await renameArchiverAccount(renameTarget.id, renameLabel.trim());
            setRenameTarget(null);
            loadAccounts();
        } catch (e: any) {
            setRenameError(e?.message || "Failed to rename archiver account");
        } finally {
            setRenameBusy(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setDeleteBusy(true);
        try {
            await deleteArchiverAccount(deleteTarget.id);
            setDeleteTarget(null);
            loadAccounts();
        } catch (e: any) {
            setError(e?.message || "Failed to delete archiver account");
        } finally {
            setDeleteBusy(false);
        }
    };

    // --- Upload export ---

    const beginUpload = (row: IArchiverAccountSummary) => {
        uploadTargetRef.current = row;
        // Reset so picking the same folder again re-fires onChange.
        if (fileInputRef.current) fileInputRef.current.value = "";
        fileInputRef.current?.click();
    };

    const onFolderSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const target = uploadTargetRef.current;
        const fileList = e.target.files;
        if (!target || !fileList || fileList.length === 0) return;

        const files = Array.from(fileList)
            .filter(f => !!f.webkitRelativePath)
            .map(f => ({relativePath: f.webkitRelativePath, file: f}));

        if (!files.some(f => f.relativePath.includes(RELATION_PATH_MARKER))) {
            setUploadTarget(target);
            setUploadPhase('error');
            setUploadError(`The selected folder has no "${RELATION_PATH_MARKER}" data — pick the export folder that contains the "connections" sub-folder.`);
            return;
        }

        const totalBytes = files.reduce((s, f) => s + f.file.size, 0);
        const stagingName = `archiver_export_${target.id}_${Date.now()}`;
        stagingNameRef.current = stagingName;
        const controller = new AbortController();
        abortRef.current = controller;

        setUploadTarget(target);
        setUploadCounts(null);
        setUploadError(null);
        setUploadPhase('uploading');
        setUploadProgress({uploaded: 0, total: totalBytes, files: files.length});

        try {
            await uploadFilesViaTus(files, {
                archiveName: stagingName,
                signal: controller.signal,
                onProgress: (uploaded, total) => setUploadProgress({uploaded, total, files: files.length}),
            });
            setUploadPhase('ingesting');
            const counts = await ingestStagedExport(target.id, stagingName);
            setUploadCounts(counts);
            setUploadPhase('done');
            loadAccounts();
        } catch (err: any) {
            const aborted = err?.name === 'AbortError';
            // Best-effort: drop partially-staged files on failure/cancel (ingest-staged
            // only cleans up on success).
            if (stagingNameRef.current) {
                server.post(`upload/staging/${stagingNameRef.current}`, {}, HTTP_METHODS.delete).catch(() => {});
            }
            setUploadError(aborted ? "Upload cancelled." : (err?.message || "Upload failed"));
            setUploadPhase('error');
        } finally {
            abortRef.current = null;
        }
    };

    const cancelUpload = () => {
        abortRef.current?.abort();
    };

    const closeUploadDialog = () => {
        if (uploadPhase === 'uploading' || uploadPhase === 'ingesting') return; // must cancel first
        setUploadTarget(null);
        stagingNameRef.current = null;
    };

    const countChip = (n: number, color: 'success' | 'warning' | 'default') =>
        n > 0 ? <Chip label={n} color={color} size="small"/> : <Typography variant="body2" color="text.disabled">0</Typography>;

    const columns: GridColDef[] = [
        {field: "label", headerName: "Label", flex: 2, minWidth: 160},
        {
            field: "following", headerName: "Following", width: 110, sortable: false,
            renderCell: (p) => countChip(p.row.counts.following, 'success'),
        },
        {
            field: "requested", headerName: "Requested", width: 110, sortable: false,
            renderCell: (p) => countChip(p.row.counts.requested, 'warning'),
        },
        {
            field: "followed_by", headerName: "Followed by", width: 120, sortable: false,
            renderCell: (p) => countChip(p.row.counts.followed_by, 'default'),
        },
        {
            field: "follow_requests_from", headerName: "Requests from", width: 130, sortable: false,
            renderCell: (p) => countChip(p.row.counts.follow_requests_from, 'default'),
        },
        {
            field: "last_import_at", headerName: "Last import", flex: 1, minWidth: 160,
            renderCell: (p) => p.value ? new Date(p.value).toLocaleString() : "Never",
        },
        {
            field: "actions", headerName: "Actions", width: 160, sortable: false,
            renderCell: (p) => (
                <Stack direction="row" gap={0.5} alignItems="center" sx={{height: "100%"}}>
                    <Tooltip title="Upload export"><IconButton size="small" color="primary" onClick={() => beginUpload(p.row)}><UploadIcon fontSize="small"/></IconButton></Tooltip>
                    <Tooltip title="Rename"><IconButton size="small" onClick={() => openRename(p.row)}><Edit fontSize="small"/></IconButton></Tooltip>
                    <Tooltip title="Delete"><IconButton size="small" color="error" onClick={() => setDeleteTarget(p.row)}><Delete fontSize="small"/></IconButton></Tooltip>
                </Stack>
            ),
        },
    ];

    const uploadBusy = uploadPhase === 'uploading' || uploadPhase === 'ingesting';
    const pct = uploadProgress.total > 0 ? Math.round((uploadProgress.uploaded / uploadProgress.total) * 100) : 0;

    return (
        <PageShell title="Archiver Accounts" subtitle={null} headerRight={
            <Button variant="contained" startIcon={<PersonAdd/>} onClick={() => setAddOpen(true)} size="small">
                Add Archiver Account
            </Button>
        }>
            {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

            <Typography variant="body2" color="text.secondary">
                Registered archiving accounts and how many target accounts each one follows, has requested,
                is followed by, or has follow requests from. Upload an Instagram "export my data" folder to
                refresh an account's data — the staged files are processed and then deleted.
            </Typography>

            <Box sx={{height: 520}}>
                <DataGrid
                    rows={accounts}
                    columns={columns}
                    loading={loading}
                    disableRowSelectionOnClick
                    density="compact"
                    pageSizeOptions={[25, 50, 100]}
                />
            </Box>

            {/* Hidden folder picker (whole-folder upload; server locates the connections data) */}
            <input
                ref={fileInputRef}
                type="file"
                // @ts-ignore — non-standard directory-picker attributes
                webkitdirectory=""
                directory=""
                multiple
                style={{display: 'none'}}
                onChange={onFolderSelected}
            />

            {/* Add dialog */}
            <Dialog open={addOpen} onClose={() => { setAddOpen(false); setAddError(null); }} maxWidth="xs" fullWidth>
                <DialogTitle>Add Archiver Account</DialogTitle>
                <DialogContent>
                    <Stack gap={2} sx={{mt: 1}}>
                        {addError && <Alert severity="error">{addError}</Alert>}
                        <FormControl variant="standard" fullWidth>
                            <InputLabel>Label</InputLabel>
                            <Input value={addLabel} onChange={(e) => setAddLabel(e.target.value)} autoFocus/>
                        </FormControl>
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => { setAddOpen(false); setAddError(null); }}>Cancel</Button>
                    <Button variant="contained" disabled={!addLabel.trim() || addBusy} onClick={handleAdd}>
                        {addBusy ? <CircularProgress size={18}/> : "Create"}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Rename dialog */}
            <Dialog open={!!renameTarget} onClose={() => setRenameTarget(null)} maxWidth="xs" fullWidth>
                <DialogTitle>Rename Archiver Account</DialogTitle>
                <DialogContent>
                    <Stack gap={2} sx={{mt: 1}}>
                        {renameError && <Alert severity="error">{renameError}</Alert>}
                        <FormControl variant="standard" fullWidth>
                            <InputLabel>Label</InputLabel>
                            <Input value={renameLabel} onChange={(e) => setRenameLabel(e.target.value)} autoFocus/>
                        </FormControl>
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setRenameTarget(null)}>Cancel</Button>
                    <Button variant="contained" disabled={!renameLabel.trim() || renameBusy} onClick={handleRename}>
                        {renameBusy ? <CircularProgress size={18}/> : "Save"}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Delete confirm */}
            <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} maxWidth="xs">
                <DialogTitle>Delete Archiver Account</DialogTitle>
                <DialogContent>
                    <Typography>
                        Permanently delete <strong>{deleteTarget?.label}</strong> and all of its access records?
                        This cannot be undone.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleteTarget(null)}>Cancel</Button>
                    <Button variant="contained" color="error" disabled={deleteBusy} onClick={handleDelete}>
                        {deleteBusy ? <CircularProgress size={18}/> : "Delete"}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Upload progress dialog */}
            <Dialog open={!!uploadTarget} onClose={closeUploadDialog} maxWidth="xs" fullWidth>
                <DialogTitle>Upload export — {uploadTarget?.label}</DialogTitle>
                <DialogContent>
                    <Stack gap={2} sx={{mt: 1}}>
                        {uploadPhase === 'error' && <Alert severity="error">{uploadError}</Alert>}
                        {uploadPhase === 'done' && uploadCounts && (
                            <Alert severity="success">
                                Imported: following {uploadCounts.following}, requested {uploadCounts.requested},
                                followed by {uploadCounts.followed_by}, requests from {uploadCounts.follow_requests_from}.
                            </Alert>
                        )}
                        {uploadBusy && (
                            <>
                                <Typography variant="body2">
                                    {uploadPhase === 'uploading'
                                        ? `Uploading ${uploadProgress.files} file(s) — ${formatBytes(uploadProgress.uploaded)} / ${formatBytes(uploadProgress.total)}`
                                        : "Processing export on the server…"}
                                </Typography>
                                <LinearProgress
                                    variant={uploadPhase === 'uploading' ? 'determinate' : 'indeterminate'}
                                    value={pct}
                                />
                            </>
                        )}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    {uploadPhase === 'uploading' && <Button color="error" onClick={cancelUpload}>Cancel</Button>}
                    {!uploadBusy && <Button variant="contained" onClick={closeUploadDialog}>Close</Button>}
                </DialogActions>
            </Dialog>
        </PageShell>
    );
}
