"""
Positive acquisition log for an archive.

`downloaded_media_log.json` at the archive root records every media asset the
archiver has acquired for the archive, keyed by canonical asset id. Acquisition
logic consults the log to decide whether to re-fetch an asset that is missing
from disk: the user "curates" an archive by simply deleting files; the log
makes those deletions stick across re-extraction runs.

File presence on disk is the source of truth for whether an asset is part of
the archive. The log is only consulted in the narrow case of "asset missing
from disk — should we re-acquire it?".
"""

import datetime
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel


LOG_FILENAME = "downloaded_media_log.json"

VideoSource = Literal["full_asset", "har_segments", "har_full_track"]
PhotoSource = Literal["full_asset", "har_image_bytes"]


class DownloadLogEntry(BaseModel):
    id: str
    kind: Literal["video", "photo"]
    filenames: list[str]
    source: str
    first_acquired_at: str
    last_acquired_at: str
    size_bytes: Optional[int] = None


class DownloadLog(BaseModel):
    videos: dict[str, DownloadLogEntry] = {}
    photos: dict[str, DownloadLogEntry] = {}


def load(archive_dir: Path) -> DownloadLog:
    p = archive_dir / LOG_FILENAME
    if not p.exists():
        return DownloadLog()
    try:
        return DownloadLog.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"⚠️  Could not parse {p.name} ({e}); starting from an empty log.")
        return DownloadLog()


def save(archive_dir: Path, log: DownloadLog) -> Path:
    p = archive_dir / LOG_FILENAME
    p.write_text(log.model_dump_json(indent=2), encoding="utf-8")
    return p


def _now() -> str:
    return datetime.datetime.now().isoformat()


def _size_of(paths: list[Path]) -> Optional[int]:
    total = 0
    saw_any = False
    for p in paths:
        try:
            if p.exists():
                total += p.stat().st_size
                saw_any = True
        except Exception:
            pass
    return total if saw_any else None


def upsert_video(
    log: DownloadLog,
    asset_id: str,
    local_files: list[Path],
    source: VideoSource,
) -> None:
    if not asset_id or not local_files:
        return
    now = _now()
    filenames = sorted({p.name for p in local_files})
    existing = log.videos.get(asset_id)
    size = _size_of(local_files)
    if existing is None:
        log.videos[asset_id] = DownloadLogEntry(
            id=asset_id,
            kind="video",
            filenames=filenames,
            source=source,
            first_acquired_at=now,
            last_acquired_at=now,
            size_bytes=size,
        )
    else:
        existing.last_acquired_at = now
        existing.filenames = sorted(set(existing.filenames) | set(filenames))
        existing.source = source
        if size is not None:
            existing.size_bytes = size


def upsert_photo(
    log: DownloadLog,
    asset_id: str,
    local_files: list[Path],
    source: PhotoSource,
) -> None:
    if not asset_id or not local_files:
        return
    now = _now()
    filenames = sorted({p.name for p in local_files})
    existing = log.photos.get(asset_id)
    size = _size_of(local_files)
    if existing is None:
        log.photos[asset_id] = DownloadLogEntry(
            id=asset_id,
            kind="photo",
            filenames=filenames,
            source=source,
            first_acquired_at=now,
            last_acquired_at=now,
            size_bytes=size,
        )
    else:
        existing.last_acquired_at = now
        existing.filenames = sorted(set(existing.filenames) | set(filenames))
        existing.source = source
        if size is not None:
            existing.size_bytes = size
