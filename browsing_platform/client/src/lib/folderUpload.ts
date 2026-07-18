import {Upload as TusUpload} from 'tus-js-client';
import cookie from 'js-cookie';
import config from '../services/config';

// ---------------------------------------------------------------------------
// Shared folder-upload helpers, used by both the archive Upload page
// (pages/Upload.tsx, tar mode) and the archiver-export page
// (pages/ArchiverAccountsPage.tsx, per-file mode). Kept here so both consume
// one implementation.
// ---------------------------------------------------------------------------

/** Auth header for raw fetch/TUS calls, matching services/server.tsx's scheme. */
export function authHeaders(): Record<string, string> {
    const token = cookie.get('token');
    return token ? {Authorization: `token:${token}`} : {};
}

/** Compute SHA-256 of a file using the browser's native Web Crypto API. */
export async function computeSha256(file: File): Promise<string> {
    const buffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    return Array.from(new Uint8Array(hashBuffer))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
}

export function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function formatDuration(s: number): string {
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ${s % 60}s`;
    return `${Math.floor(m / 60)}h ${m % 60}m`;
}

/** Run async task thunks with a bounded concurrency limit. */
export async function runConcurrently<T>(
    tasks: (() => Promise<T>)[],
    limit: number,
): Promise<PromiseSettledResult<T>[]> {
    const results: Promise<T>[] = [];
    const executing = new Set<Promise<T>>();
    for (const task of tasks) {
        const p = Promise.resolve().then(task);
        results.push(p);
        executing.add(p);
        p.finally(() => executing.delete(p));
        while (executing.size >= limit) await Promise.race(executing).catch(() => {});
    }
    return Promise.allSettled(results);
}

export interface UploadFilesOptions {
    /** TUS `archiveName` metadata — the staging folder name under the upload staging dir. */
    archiveName: string;
    /** Reports cumulative bytes uploaded across all files (0..totalBytes). */
    onProgress?: (uploadedBytes: number, totalBytes: number) => void;
    signal?: AbortSignal;
    concurrency?: number;
    chunkSize?: number;
}

/**
 * Upload a set of files via the TUS endpoints in per-file mode: each file is a
 * separate TUS upload carrying its `relativePath` metadata, so the server
 * reconstructs the directory tree under `<staging>/<archiveName>/`. Rejects if
 * any file fails or the signal aborts.
 */
export async function uploadFilesViaTus(
    files: ReadonlyArray<{ relativePath: string; file: File }>,
    opts: UploadFilesOptions,
): Promise<void> {
    const totalBytes = files.reduce((s, f) => s + f.file.size, 0);
    const perFileUploaded = new Map<string, number>();

    const report = () => {
        if (!opts.onProgress) return;
        let sum = 0;
        for (const v of perFileUploaded.values()) sum += v;
        opts.onProgress(sum, totalBytes);
    };

    const tasks = files.map(f => () => new Promise<void>((resolve, reject) => {
        if (opts.signal?.aborted) {
            reject(new DOMException('Aborted', 'AbortError'));
            return;
        }
        const upload = new TusUpload(f.file, {
            endpoint: `${config.serverPath}api/upload/tus/`,
            chunkSize: opts.chunkSize ?? 5 * 1024 * 1024,
            retryDelays: [0, 1000, 3000, 5000, 10000],
            removeFingerprintOnSuccess: true,
            metadata: {archiveName: opts.archiveName, relativePath: f.relativePath},
            headers: authHeaders(),
            onProgress: (uploaded: number) => {
                perFileUploaded.set(f.relativePath, uploaded);
                report();
            },
            onSuccess: () => {
                perFileUploaded.set(f.relativePath, f.file.size);
                report();
                resolve();
            },
            onError: (err: Error) => reject(err),
        });
        opts.signal?.addEventListener('abort', () => {
            upload.abort(true).catch(() => {});
            reject(new DOMException('Aborted', 'AbortError'));
        }, {once: true});
        upload.start();
    }));

    const results = await runConcurrently(tasks, opts.concurrency ?? 6);
    const failed = results.find((r): r is PromiseRejectedResult => r.status === 'rejected');
    if (failed) throw failed.reason;
}
