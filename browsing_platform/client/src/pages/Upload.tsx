import React, {useCallback, useEffect, useRef, useState} from 'react';
import {Upload as TusUpload} from 'tus-js-client';
import cookie from 'js-cookie';
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Collapse,
    FormControlLabel,
    IconButton,
    LinearProgress,
    Pagination,
    Radio,
    RadioGroup,
    Stack,
    Switch,
    Tooltip,
    Typography,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import UnfoldLessIcon from '@mui/icons-material/UnfoldLess';
import UnfoldMoreIcon from '@mui/icons-material/UnfoldMore';
import CreateNewFolderIcon from '@mui/icons-material/CreateNewFolder';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import TopNavBar from '../UIComponents/TopNavBar/TopNavBar';
import config from '../services/config';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Phase = 'idle' | 'scanning' | 'setup' | 'uploading' | 'done';

interface FileState {
    relativePath: string;
    file: File;
    uploadedBytes: number;
    status: 'pending' | 'hashing' | 'uploading' | 'done' | 'error';
    error?: string;
}

interface VerifyResult {
    status: 'pass' | 'fail' | 'no_checksum_file';
    results: { path: string; status: string }[];
}

interface ArchiveState {
    name: string;
    files: FileState[];
    totalBytes: number;
    uploadedBytes: number;
    hasConflict: boolean;
    resolution: 'skip' | 'overwrite';
    status: 'pending' | 'uploading' | 'verifying' | 'done' | 'failed' | 'skipped';
    verifyResult?: VerifyResult;
    expanded: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function readAllDirEntries(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
    const entries: FileSystemEntry[] = [];
    while (true) {
        const batch = await new Promise<FileSystemEntry[]>((res, rej) => reader.readEntries(res, rej));
        if (!batch.length) break;
        entries.push(...batch);
    }
    return entries;
}

async function collectFiles(entry: FileSystemEntry, prefix: string): Promise<{ relativePath: string; file: File }[]> {
    const currentPath = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isFile) {
        const file = await new Promise<File>((res, rej) => (entry as FileSystemFileEntry).file(res, rej));
        return [{ relativePath: currentPath, file }];
    }
    const children = await readAllDirEntries((entry as FileSystemDirectoryEntry).createReader());
    const results = await Promise.all(children.map(c => collectFiles(c, currentPath)));
    return results.flat();
}

/** Compute SHA-256 of a file using the browser's native Web Crypto API. */
async function computeSha256(file: File): Promise<string> {
    const buffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    return Array.from(new Uint8Array(hashBuffer))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
}

function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatDuration(s: number): string {
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ${s % 60}s`;
    return `${Math.floor(m / 60)}h ${m % 60}m`;
}

function authHeaders(): Record<string, string> {
    const token = cookie.get('token');
    return token ? { Authorization: `token:${token}` } : {};
}

async function apiPost(path: string, body?: object): Promise<any> {
    const res = await fetch(`${config.serverPath}api/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
    return res.json();
}

async function apiDelete(path: string): Promise<void> {
    await fetch(`${config.serverPath}api/${path}`, {
        method: 'DELETE',
        headers: authHeaders(),
    });
}

// Semaphore-style upload pool for concurrency limiting
class UploadPool {
    private active = 0;
    private queue: (() => void)[] = [];
    constructor(private max: number) {}
    async run<T>(task: () => Promise<T>): Promise<T> {
        await this._acquire();
        try { return await task(); } finally { this._release(); }
    }
    private _acquire(): Promise<void> {
        if (this.active < this.max) { this.active++; return Promise.resolve(); }
        return new Promise(r => this.queue.push(() => { this.active++; r(); }));
    }
    private _release() { this.active--; this.queue.shift()?.(); }
}

const ITEMS_PER_PAGE = 10;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function UploadPage() {
    const [phase, setPhase] = useState<Phase>('idle');
    const [archives, setArchives] = useState<ArchiveState[]>([]);
    const [scanError, setScanError] = useState<string | null>(null);
    const [hideSkipped, setHideSkipped] = useState(false);
    const [currentPage, setCurrentPage] = useState(1);
    const [isDragActive, setIsDragActive] = useState(false);
    const [elapsedSeconds, setElapsedSeconds] = useState(0);

    // Refs shared with async upload callbacks
    const activeUploadsRef = useRef<Map<string, TusUpload>>(new Map());
    const cancelledRef = useRef(false);
    const dragCounterRef = useRef(0);
    const pageContainerRef = useRef<HTMLDivElement>(null);
    const uploadStartTimeRef = useRef<number>(0);
    const speedSamplesRef = useRef<{ time: number; bytes: number }[]>([]);
    const elapsedIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const isUploading = phase === 'uploading';

    // Warn on browser close / refresh while uploading
    useEffect(() => {
        if (!isUploading) return;
        const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); };
        window.addEventListener('beforeunload', handler);
        return () => window.removeEventListener('beforeunload', handler);
    }, [isUploading]);

    // Abort active TUS transfers if the component unmounts mid-upload (in-app navigation)
    useEffect(() => {
        return () => {
            if (activeUploadsRef.current.size > 0) {
                cancelledRef.current = true;
                for (const upload of activeUploadsRef.current.values()) {
                    Promise.resolve(upload.abort(true)).catch(() => {});
                }
                activeUploadsRef.current.clear();
            }
            if (elapsedIntervalRef.current) clearInterval(elapsedIntervalRef.current);
        };
    }, []);

    // Collect speed samples during upload (sliding 60s window)
    useEffect(() => {
        if (phase !== 'uploading') return;
        const totalUploaded = archives.reduce((s, a) => s + a.uploadedBytes, 0);
        const now = Date.now();
        speedSamplesRef.current.push({ time: now, bytes: totalUploaded });
        speedSamplesRef.current = speedSamplesRef.current.filter(s => s.time >= now - 60_000);
    }, [archives, phase]);

    // -----------------------------------------------------------------------
    // State helpers (always use functional updates to avoid stale closures)
    // -----------------------------------------------------------------------

    const setFileStatus = (archiveName: string, filePath: string, update: Partial<FileState>) =>
        setArchives(prev => prev.map(a =>
            a.name !== archiveName ? a : (() => {
                const files = a.files.map(f => f.relativePath === filePath ? { ...f, ...update } : f);
                const uploadedBytes = files.reduce((s, f) => s + f.uploadedBytes, 0);
                return { ...a, files, uploadedBytes };
            })()
        ));

    const setArchiveStatus = (archiveName: string, update: Partial<ArchiveState>) =>
        setArchives(prev => prev.map(a => a.name !== archiveName ? a : { ...a, ...update }));

    // -----------------------------------------------------------------------
    // Drop handling (full-page)
    // -----------------------------------------------------------------------

    const handlePageDragEnter = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        dragCounterRef.current += 1;
        if (dragCounterRef.current === 1) setIsDragActive(true);
    }, []);

    const handlePageDragLeave = useCallback(() => {
        dragCounterRef.current -= 1;
        if (dragCounterRef.current === 0) setIsDragActive(false);
    }, []);

    const handlePageDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
    }, []);

    const handlePageDrop = useCallback(async (e: React.DragEvent) => {
        e.preventDefault();
        dragCounterRef.current = 0;
        setIsDragActive(false);
        if (phase !== 'idle') return;

        setScanError(null);
        setPhase('scanning');

        try {
            const items = Array.from(e.dataTransfer.items);
            const dirEntries = items
                .map(item => item.webkitGetAsEntry())
                .filter((entry): entry is FileSystemDirectoryEntry => !!entry && entry.isDirectory);

            if (!dirEntries.length) {
                setScanError('No folders detected. Please drop one or more archive folders.');
                setPhase('idle');
                return;
            }

            // Collect all files per archive
            const archiveList: ArchiveState[] = [];
            for (const archiveEntry of dirEntries) {
                const children = await readAllDirEntries(archiveEntry.createReader());
                const flat = await Promise.all(children.map(c => collectFiles(c, '')));
                const fileList = flat.flat();
                const files: FileState[] = fileList.map(({ relativePath, file }) => ({
                    relativePath,
                    file,
                    uploadedBytes: 0,
                    status: 'pending',
                }));
                const totalBytes = files.reduce((s, f) => s + f.file.size, 0);
                archiveList.push({
                    name: archiveEntry.name,
                    files,
                    totalBytes,
                    uploadedBytes: 0,
                    hasConflict: false,
                    resolution: 'skip',
                    status: 'pending',
                    expanded: false,
                });
            }

            // Preflight conflict check
            const preflight = await apiPost('upload/preflight', {
                archives: archiveList.map(a => a.name),
            });
            const conflicts: Record<string, boolean> = preflight.conflicts ?? {};

            setArchives(archiveList.map(a => ({
                ...a,
                hasConflict: !!conflicts[a.name],
                resolution: conflicts[a.name] ? 'skip' : 'overwrite',
            })));
            setHideSkipped(false);
            setCurrentPage(1);
            setPhase('setup');
        } catch (err) {
            setScanError(`Failed to scan folders: ${err instanceof Error ? err.message : String(err)}`);
            setPhase('idle');
        }
    }, [phase]);

    // -----------------------------------------------------------------------
    // Bulk conflict toggle
    // -----------------------------------------------------------------------

    const bulkAllSkip = archives.filter(a => a.hasConflict).every(a => a.resolution === 'skip');

    const toggleBulkResolution = () => {
        const newResolution = bulkAllSkip ? 'overwrite' : 'skip';
        setArchives(prev => prev.map(a => a.hasConflict ? { ...a, resolution: newResolution } : a));
    };

    // -----------------------------------------------------------------------
    // Upload
    // -----------------------------------------------------------------------

    const startUpload = async () => {
        cancelledRef.current = false;

        // Start elapsed timer
        uploadStartTimeRef.current = Date.now();
        speedSamplesRef.current = [];
        setElapsedSeconds(0);
        elapsedIntervalRef.current = setInterval(() =>
            setElapsedSeconds(Math.floor((Date.now() - uploadStartTimeRef.current) / 1000)),
            1000
        );

        setPhase('uploading');

        const pool = new UploadPool(3); // 3 concurrent file uploads across all archives

        const archivesToUpload = archives.filter(a => a.resolution !== 'skip' || !a.hasConflict);

        // Mark skipped archives
        setArchives(prev => prev.map(a =>
            (a.hasConflict && a.resolution === 'skip') ? { ...a, status: 'skipped' } : a
        ));

        const uploadFile = (archiveName: string, fileEntry: FileState): Promise<void> =>
            pool.run(async () => {
                if (cancelledRef.current) throw new Error('cancelled');

                // Hash the file before uploading so the server can verify integrity
                setFileStatus(archiveName, fileEntry.relativePath, { status: 'hashing' });
                const fileHash = await computeSha256(fileEntry.file);

                if (cancelledRef.current) throw new Error('cancelled');

                return new Promise<void>((resolve, reject) => {
                const upload = new TusUpload(fileEntry.file, {
                    endpoint: `${config.serverPath}api/upload/tus/`,
                    chunkSize: 5 * 1024 * 1024,
                    retryDelays: [0, 1000, 3000, 5000, 10000],
                    metadata: { archiveName, relativePath: fileEntry.relativePath, fileHash },
                    headers: authHeaders(),
                    onProgress: (uploaded) => {
                        setFileStatus(archiveName, fileEntry.relativePath, {
                            uploadedBytes: uploaded,
                            status: 'uploading',
                        });
                    },
                    onSuccess: () => {
                        setFileStatus(archiveName, fileEntry.relativePath, { status: 'done' });
                        activeUploadsRef.current.delete(`${archiveName}:${fileEntry.relativePath}`);
                        resolve();
                    },
                    onError: (err) => {
                        const msg = err instanceof Error ? err.message : String(err);
                        setFileStatus(archiveName, fileEntry.relativePath, { status: 'error', error: msg });
                        activeUploadsRef.current.delete(`${archiveName}:${fileEntry.relativePath}`);
                        reject(err);
                    },
                });

                activeUploadsRef.current.set(`${archiveName}:${fileEntry.relativePath}`, upload);
                upload.start();
                }); // end new Promise
            }); // end pool.run async

        const processArchive = async (archive: ArchiveState) => {
            if (cancelledRef.current) return;
            setArchiveStatus(archive.name, { status: 'uploading' });

            // If overwriting an existing archive, clean up any leftover staging first
            if (archive.hasConflict && archive.resolution === 'overwrite') {
                await apiDelete(`upload/staging/${archive.name}`).catch(() => {});
            }

            // Upload all files (pool limits total concurrency)
            const results = await Promise.allSettled(
                archive.files.map(f => uploadFile(archive.name, f))
            );

            if (cancelledRef.current) return;

            const anyError = results.some(r => r.status === 'rejected');
            if (anyError) {
                setArchiveStatus(archive.name, { status: 'failed' });
                return;
            }

            // Verify checksums
            setArchiveStatus(archive.name, { status: 'verifying' });
            try {
                const verifyResult: VerifyResult = await apiPost(`upload/verify/${archive.name}`);
                if (verifyResult.status === 'pass' || verifyResult.status === 'no_checksum_file') {
                    await apiPost(`upload/commit/${archive.name}`);
                    setArchiveStatus(archive.name, { status: 'done', verifyResult });
                } else {
                    setArchiveStatus(archive.name, { status: 'failed', verifyResult });
                }
            } catch (err) {
                setArchiveStatus(archive.name, {
                    status: 'failed',
                    verifyResult: { status: 'fail', results: [{ path: '', status: `Error: ${err}` }] },
                });
            }
        };

        // All archives run concurrently (file-level concurrency is governed by the pool)
        await Promise.allSettled(archivesToUpload.map(processArchive));

        if (elapsedIntervalRef.current) {
            clearInterval(elapsedIntervalRef.current);
            elapsedIntervalRef.current = null;
        }

        if (!cancelledRef.current) {
            setPhase('done');
        }
    };

    // -----------------------------------------------------------------------
    // Cancel
    // -----------------------------------------------------------------------

    const cancel = async () => {
        cancelledRef.current = true;
        dragCounterRef.current = 0;
        setIsDragActive(false);

        if (elapsedIntervalRef.current) {
            clearInterval(elapsedIntervalRef.current);
            elapsedIntervalRef.current = null;
        }

        // Abort all active TUS uploads
        for (const upload of activeUploadsRef.current.values()) {
            Promise.resolve(upload.abort(true)).catch(() => {});
        }
        activeUploadsRef.current.clear();

        // Clean up staging directories for archives that were in progress
        const inProgress = archives.filter(a => a.status === 'uploading' || a.status === 'verifying');
        await Promise.allSettled(
            inProgress.map(a => apiDelete(`upload/staging/${a.name}`).catch(() => {}))
        );

        setArchives([]);
        setPhase('idle');
    };

    // -----------------------------------------------------------------------
    // Retry failed archives
    // -----------------------------------------------------------------------

    const retryFailed = () => {
        dragCounterRef.current = 0;
        setArchives(prev => prev.map(a =>
            a.status === 'failed' ? {
                ...a,
                status: 'pending',
                uploadedBytes: 0,
                files: a.files.map(f => ({ ...f, uploadedBytes: 0, status: 'pending', error: undefined })),
                verifyResult: undefined,
            } : a
        ));
        setCurrentPage(1);
        setPhase('setup');
    };

    // -----------------------------------------------------------------------
    // Derived values for upload phase
    // -----------------------------------------------------------------------

    const totalBytesToUpload = archives
        .filter(a => a.status !== 'skipped')
        .reduce((s, a) => s + a.totalBytes, 0);
    const totalBytesUploaded = archives
        .filter(a => a.status !== 'skipped')
        .reduce((s, a) => s + a.uploadedBytes, 0);
    const overallPct = totalBytesToUpload > 0
        ? Math.round((totalBytesUploaded / totalBytesToUpload) * 100)
        : 0;

    const samples = speedSamplesRef.current;
    let speedBytesPerSec = 0;
    let etaSeconds: number | null = null;
    if (samples.length >= 2) {
        const dt = (samples[samples.length - 1].time - samples[0].time) / 1000;
        if (dt > 0) {
            speedBytesPerSec = (samples[samples.length - 1].bytes - samples[0].bytes) / dt;
            const remaining = totalBytesToUpload - totalBytesUploaded;
            etaSeconds = speedBytesPerSec > 0 ? Math.ceil(remaining / speedBytesPerSec) : null;
        }
    }

    // -----------------------------------------------------------------------
    // Render helpers
    // -----------------------------------------------------------------------

    const statusChip = (status: ArchiveState['status']) => {
        const map: Record<string, { label: string; color: 'default' | 'info' | 'warning' | 'success' | 'error' }> = {
            pending: { label: 'Pending', color: 'default' },
            uploading: { label: 'Uploading', color: 'info' },
            verifying: { label: 'Verifying', color: 'warning' },
            done: { label: 'Done', color: 'success' },
            failed: { label: 'Failed', color: 'error' },
            skipped: { label: 'Skipped', color: 'default' },
        };
        const { label, color } = map[status] ?? { label: status, color: 'default' };
        return <Chip label={label} color={color} size="small" />;
    };

    const pct = (a: ArchiveState) =>
        a.totalBytes > 0 ? Math.round((a.uploadedBytes / a.totalBytes) * 100) : 0;

    const doneSummary = () => {
        const done = archives.filter(a => a.status === 'done').length;
        const failed = archives.filter(a => a.status === 'failed').length;
        const skipped = archives.filter(a => a.status === 'skipped').length;
        return { done, failed, skipped };
    };

    // -----------------------------------------------------------------------
    // Pagination helpers
    // -----------------------------------------------------------------------

    const hasAnySkipped = archives.some(a => a.hasConflict && a.resolution === 'skip');

    const visibleSetupArchives = hideSkipped
        ? archives.filter(a => !(a.hasConflict && a.resolution === 'skip'))
        : archives;

    const setupPageItems = visibleSetupArchives.slice(
        (currentPage - 1) * ITEMS_PER_PAGE,
        currentPage * ITEMS_PER_PAGE
    );

    const uploadingPageItems = archives.slice(
        (currentPage - 1) * ITEMS_PER_PAGE,
        currentPage * ITEMS_PER_PAGE
    );

    const donePageItems = archives.slice(
        (currentPage - 1) * ITEMS_PER_PAGE,
        currentPage * ITEMS_PER_PAGE
    );

    const renderPagination = (totalCount: number) =>
        totalCount > ITEMS_PER_PAGE ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', pt: 1 }}>
                <Pagination
                    count={Math.ceil(totalCount / ITEMS_PER_PAGE)}
                    page={currentPage}
                    onChange={(_, p) => setCurrentPage(p)}
                    color="primary"
                />
            </Box>
        ) : null;

    // -----------------------------------------------------------------------
    // Render
    // -----------------------------------------------------------------------

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
            <TopNavBar>
                <Typography variant="h6" sx={{ color: 'white' }}>Upload Archives</Typography>
            </TopNavBar>

            {/* Scroll container — also the full-page drag target */}
            <Box
                ref={pageContainerRef}
                onDragEnter={handlePageDragEnter}
                onDragLeave={handlePageDragLeave}
                onDragOver={handlePageDragOver}
                onDrop={handlePageDrop}
                sx={{ flex: 1, overflow: 'auto', position: 'relative' }}
            >
                <Box sx={{ maxWidth: 900, mx: 'auto', p: 3 }}>

                    {/* ── IDLE ── */}
                    {phase === 'idle' && (
                        <Box
                            sx={{
                                border: '2px dashed',
                                borderColor: 'divider',
                                borderRadius: 2,
                                p: 8,
                                textAlign: 'center',
                                cursor: 'copy',
                                transition: 'border-color 0.2s',
                                '&:hover': { borderColor: 'primary.main' },
                            }}
                        >
                            <CloudUploadIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
                            <Typography variant="h6" gutterBottom>Drop archive folders here</Typography>
                            <Typography variant="body2" color="text.secondary">
                                You can drop multiple archive folders at once.
                            </Typography>
                            {scanError && <Alert severity="error" sx={{ mt: 2 }}>{scanError}</Alert>}
                        </Box>
                    )}

                    {/* ── SCANNING ── */}
                    {phase === 'scanning' && (
                        <Stack alignItems="center" gap={2} sx={{ py: 8 }}>
                            <CircularProgress />
                            <Typography>Scanning folder structure…</Typography>
                        </Stack>
                    )}

                    {/* ── SETUP ── */}
                    {phase === 'setup' && (
                        <Stack gap={2}>
                            {/* Header */}
                            <Stack direction="row" alignItems="baseline" gap={1}>
                                <Typography variant="h6">
                                    {archives.length} archive{archives.length !== 1 ? 's' : ''} detected
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    ({archives.reduce((s, a) => s + a.files.length, 0)} files,{' '}
                                    {formatBytes(archives.reduce((s, a) => s + a.totalBytes, 0))} total)
                                </Typography>
                            </Stack>

                            {/* Action buttons — always at top */}
                            <Stack direction="row" gap={2}>
                                <Button variant="contained" size="large" onClick={startUpload}>
                                    Start Upload
                                </Button>
                                <Button variant="outlined" onClick={() => { setArchives([]); setPhase('idle'); }}>
                                    Cancel
                                </Button>
                            </Stack>

                            {/* Conflict alert */}
                            {archives.some(a => a.hasConflict) && (
                                <Alert
                                    severity="warning"
                                    action={
                                        <FormControlLabel
                                            control={
                                                <Tooltip title={bulkAllSkip
                                                    ? 'Existing archives will be skipped'
                                                    : 'Existing archives will be overridden'
                                                }>
                                                    <Switch checked={!bulkAllSkip} onChange={toggleBulkResolution} />
                                                </Tooltip>
                                            }
                                            label="Re-upload existing archives"
                                            sx={{ mr: 0 }}
                                        />
                                    }
                                >
                                    Some archives already exist in the destination.
                                </Alert>
                            )}

                            {/* Hide skipped button */}
                            {archives.some(a => a.hasConflict) && (
                                <Box>
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        startIcon={<VisibilityOffIcon />}
                                        disabled={!hasAnySkipped}
                                        onClick={() => { setHideSkipped(p => !p); setCurrentPage(1); }}
                                    >
                                        {hideSkipped ? 'Show skipped' : 'Hide skipped'}
                                    </Button>
                                </Box>
                            )}

                            {/* Archive cards (paginated) */}
                            {setupPageItems.map(archive => (
                                <Card key={archive.name} variant="outlined">
                                    <CardContent>
                                        <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1}>
                                            <Stack gap={0.5}>
                                                <Typography variant="subtitle1" fontWeight="bold">{archive.name}</Typography>
                                                <Typography variant="body2" color="text.secondary">
                                                    {archive.files.length} files · {formatBytes(archive.totalBytes)}
                                                </Typography>
                                            </Stack>
                                            {archive.hasConflict ? (
                                                <Stack direction="row" alignItems="center" gap={1}>
                                                    <Chip label="Already exists" color="warning" size="small" icon={<WarningIcon />} />
                                                    <RadioGroup
                                                        row
                                                        value={archive.resolution}
                                                        onChange={(_, v) => setArchiveStatus(archive.name, { resolution: v as 'skip' | 'overwrite' })}
                                                    >
                                                        <FormControlLabel value="skip" control={<Radio size="small" />} label="Skip" />
                                                        <FormControlLabel value="overwrite" control={<Radio size="small" />} label="Overwrite" />
                                                    </RadioGroup>
                                                </Stack>
                                            ) : <Chip label="New archive" color="primary" size="small" icon={<CreateNewFolderIcon />} />}
                                        </Stack>
                                    </CardContent>
                                </Card>
                            ))}

                            {renderPagination(visibleSetupArchives.length)}
                        </Stack>
                    )}

                    {/* ── UPLOADING ── */}
                    {phase === 'uploading' && (
                        <Stack gap={2}>
                            {/* Cancel — always visible above accordion */}
                            <Stack direction="row" justifyContent="space-between" alignItems="center">
                                <Typography variant="h6">Uploading…</Typography>
                                <Button color="error" variant="outlined" onClick={cancel}>Cancel</Button>
                            </Stack>

                            <Accordion defaultExpanded={false} disableGutters>
                                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                    <Stack sx={{ width: '100%', pr: 1 }} gap={0.5}>
                                        <Tooltip title={speedBytesPerSec > 0
                                            ? `${formatBytes(Math.round(speedBytesPerSec))}/s`
                                            : 'Calculating speed…'
                                        }>
                                            <span>
                                                <LinearProgress
                                                    variant="determinate"
                                                    value={overallPct}
                                                    sx={{ height: 8, borderRadius: 1 }}
                                                />
                                            </span>
                                        </Tooltip>
                                        <Stack direction="row" justifyContent="space-between">
                                            <Typography variant="caption" color="text.secondary">
                                                {formatBytes(totalBytesUploaded)} / {formatBytes(totalBytesToUpload)} ({overallPct}%)
                                            </Typography>
                                            <Stack direction="row" gap={2}>
                                                <Typography variant="caption" color="text.secondary">
                                                    Elapsed: {formatDuration(elapsedSeconds)}
                                                </Typography>
                                                {etaSeconds !== null && (
                                                    <Typography variant="caption" color="text.secondary">
                                                        ETA: {formatDuration(etaSeconds)}
                                                    </Typography>
                                                )}
                                            </Stack>
                                        </Stack>
                                    </Stack>
                                </AccordionSummary>

                                <AccordionDetails sx={{ p: 0 }}>
                                    {/* Collapse all / Expand all */}
                                    <Stack direction="row" justifyContent="flex-end" gap={1} sx={{ px: 2, pb: 1 }}>
                                        <Button
                                            size="small"
                                            startIcon={<UnfoldLessIcon />}
                                            onClick={() => setArchives(prev => prev.map(a => ({ ...a, expanded: false })))}
                                        >
                                            Collapse all
                                        </Button>
                                        <Button
                                            size="small"
                                            startIcon={<UnfoldMoreIcon />}
                                            onClick={() => setArchives(prev => prev.map(a => ({ ...a, expanded: true })))}
                                        >
                                            Expand all
                                        </Button>
                                    </Stack>

                                    <Stack gap={1} sx={{ px: 2, pb: 1 }}>
                                        {uploadingPageItems.map(archive => (
                                            <Card key={archive.name} variant="outlined">
                                                <CardContent>
                                                    <Stack direction="row" alignItems="center" gap={1} mb={1}>
                                                        <Typography variant="subtitle1" fontWeight="bold" sx={{ flex: 1 }}>
                                                            {archive.name}
                                                        </Typography>
                                                        {statusChip(archive.status)}
                                                        {(archive.status === 'uploading' || archive.status === 'verifying') && (
                                                            <CircularProgress size={16} />
                                                        )}
                                                        <Tooltip title={archive.expanded ? 'Hide files' : 'Show files'}>
                                                            <IconButton size="small" onClick={() => setArchiveStatus(archive.name, { expanded: !archive.expanded })}>
                                                                {archive.expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                                                            </IconButton>
                                                        </Tooltip>
                                                    </Stack>

                                                    {archive.status !== 'skipped' && (
                                                        <>
                                                            <LinearProgress
                                                                variant="determinate"
                                                                value={pct(archive)}
                                                                sx={{ mb: 0.5 }}
                                                            />
                                                            <Typography variant="caption" color="text.secondary">
                                                                {formatBytes(archive.uploadedBytes)} / {formatBytes(archive.totalBytes)} ({pct(archive)}%)
                                                            </Typography>
                                                        </>
                                                    )}

                                                    {archive.status === 'failed' && archive.verifyResult && (
                                                        <Alert severity="error" sx={{ mt: 1 }}>
                                                            Checksum verification failed for{' '}
                                                            {archive.verifyResult.results.filter(r => r.status !== 'pass').length} file(s).
                                                        </Alert>
                                                    )}

                                                    <Collapse in={archive.expanded}>
                                                        <Stack gap={0.5} mt={1}>
                                                            {archive.files.map(f => (
                                                                <Stack key={f.relativePath} direction="row" alignItems="center" gap={1}>
                                                                    {f.status === 'done' && <CheckCircleIcon fontSize="small" color="success" />}
                                                                    {f.status === 'error' && <ErrorIcon fontSize="small" color="error" />}
                                                                    {(f.status === 'uploading' || f.status === 'hashing' || f.status === 'pending') && (
                                                                        <Box sx={{ width: 20, display: 'flex', justifyContent: 'center' }}>
                                                                            {(f.status === 'uploading' || f.status === 'hashing')
                                                                                ? <CircularProgress size={14} />
                                                                                : <Box sx={{ width: 14, height: 14 }} />}
                                                                        </Box>
                                                                    )}
                                                                    <Typography variant="caption" sx={{ flex: 1, fontFamily: 'monospace' }}>
                                                                        {f.relativePath}
                                                                    </Typography>
                                                                    <Typography variant="caption" color="text.secondary">
                                                                        {f.status === 'hashing'
                                                                            ? 'Hashing…'
                                                                            : `${formatBytes(f.uploadedBytes)} / ${formatBytes(f.file.size)}`}
                                                                    </Typography>
                                                                </Stack>
                                                            ))}
                                                        </Stack>
                                                    </Collapse>
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </Stack>

                                    {renderPagination(archives.length)}
                                </AccordionDetails>
                            </Accordion>
                        </Stack>
                    )}

                    {/* ── DONE ── */}
                    {phase === 'done' && (() => {
                        const { done, failed, skipped } = doneSummary();
                        const totalTransferred = archives
                            .filter(a => a.status === 'done')
                            .reduce((s, a) => s + a.totalBytes, 0);
                        return (
                            <Stack gap={2}>
                                <Typography variant="h6">Upload complete</Typography>
                                <Stack direction="row" gap={1}>
                                    {done > 0 && <Chip label={`${done} uploaded`} color="success" icon={<CheckCircleIcon />} />}
                                    {failed > 0 && <Chip label={`${failed} failed`} color="error" icon={<ErrorIcon />} />}
                                    {skipped > 0 && <Chip label={`${skipped} skipped`} color="default" />}
                                </Stack>
                                {totalTransferred > 0 && (
                                    <Typography variant="body2" color="text.secondary">
                                        Total data transferred: {formatBytes(totalTransferred)}
                                    </Typography>
                                )}

                                {donePageItems.map(archive => (
                                    <Card key={archive.name} variant="outlined">
                                        <CardContent>
                                            <Stack direction="row" alignItems="center" gap={1}>
                                                <Typography variant="subtitle1" fontWeight="bold" sx={{ flex: 1 }}>
                                                    {archive.name}
                                                </Typography>
                                                {statusChip(archive.status)}
                                            </Stack>
                                            {archive.verifyResult?.status === 'fail' && (
                                                <Alert severity="error" sx={{ mt: 1 }}>
                                                    <Typography variant="body2" fontWeight="bold">Failed files:</Typography>
                                                    {archive.verifyResult.results
                                                        .filter(r => r.status !== 'pass')
                                                        .map(r => (
                                                            <Typography key={r.path} variant="caption" component="div" fontFamily="monospace">
                                                                {r.path} — {r.status}
                                                            </Typography>
                                                        ))}
                                                </Alert>
                                            )}
                                        </CardContent>
                                    </Card>
                                ))}

                                {renderPagination(archives.length)}

                                <Stack direction="row" gap={2}>
                                    <Button variant="outlined" onClick={() => { setArchives([]); setPhase('idle'); }}>
                                        Upload more
                                    </Button>
                                    {failed > 0 && (
                                        <Button variant="contained" color="warning" onClick={retryFailed}>
                                            Retry failed
                                        </Button>
                                    )}
                                </Stack>
                            </Stack>
                        );
                    })()}
                </Box>

                {/* Full-page drag overlay */}
                {isDragActive && phase === 'idle' && (
                    <Box sx={{
                        position: 'absolute',
                        inset: 0,
                        border: '4px dashed',
                        borderColor: 'primary.main',
                        borderRadius: 2,
                        bgcolor: 'rgba(25, 118, 210, 0.08)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 10,
                        pointerEvents: 'none',
                    }}>
                        <Stack alignItems="center" gap={2}>
                            <CloudUploadIcon sx={{ fontSize: 80, color: 'primary.main' }} />
                            <Typography variant="h5" color="primary">Drop archive folders here</Typography>
                        </Stack>
                    </Box>
                )}
            </Box>
        </Box>
    );
}
