import hashlib
import json
import logging
import os
import re
import shutil
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_ARCHIVE_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_\-]*$')
_TUS_STATE_DIR = ".tus_state"


def get_staging_dir() -> Path:
    custom = os.getenv("UPLOAD_STAGING_DIR")
    return Path(custom) if custom else Path("archives") / ".upload_staging"


def validate_archive_name(name: str) -> bool:
    return bool(name) and len(name) <= 200 and bool(_ARCHIVE_NAME_RE.match(name))


def validate_file_path(relative_path: str) -> bool:
    if not relative_path or len(relative_path) > 1000:
        return False
    p = Path(relative_path)
    if p.is_absolute():
        return False
    for part in p.parts:
        if part in ('..', '.', ''):
            return False
    return True


def _safe_staging_file_path(archive_name: str, relative_path: str) -> Path:
    """Resolve file path and assert it stays inside the staging archive dir."""
    staging = get_staging_dir()
    base = (staging / archive_name).resolve()
    target = (base / relative_path).resolve()
    if not str(target).startswith(str(base) + os.sep):
        raise ValueError("Path traversal detected")
    return target


def check_conflicts(archive_names: list[str]) -> dict[str, bool]:
    return {name: (Path("archives") / name).exists() for name in archive_names}


def create_upload(archive_name: str, relative_path: str, upload_length: int, file_hash: Optional[str]) -> str:
    """Create a new TUS upload session. Returns the file_id.

    file_hash: hex-encoded SHA-256 of the complete file, computed by the client
               before upload. Stored in state and verified after all chunks land.
    """
    staging = get_staging_dir()
    file_id = uuid.uuid4().hex

    state_dir = staging / archive_name / _TUS_STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)

    file_path = _safe_staging_file_path(archive_name, relative_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    # Create empty file (overwrite any leftover from a previous partial upload)
    file_path.open("wb").close()

    state = {
        "file_id": file_id,
        "archive_name": archive_name,
        "relative_path": relative_path,
        "upload_length": upload_length,
        "file_hash": file_hash,  # SHA-256 declared by client; None if not provided
        "offset": 0,
    }
    (state_dir / f"{file_id}.json").write_text(json.dumps(state), encoding="utf-8")
    return file_id


def _find_state_file(file_id: str) -> Optional[Path]:
    staging = get_staging_dir()
    if not staging.exists():
        return None
    for archive_dir in staging.iterdir():
        if not archive_dir.is_dir():
            continue
        candidate = archive_dir / _TUS_STATE_DIR / f"{file_id}.json"
        if candidate.exists():
            return candidate
    return None


def get_upload_state(file_id: str) -> Optional[dict]:
    state_file = _find_state_file(file_id)
    return json.loads(state_file.read_text(encoding="utf-8")) if state_file else None


def patch_upload(file_id: str, offset: int, data: bytes) -> int:
    """Append a chunk. Returns the new offset."""
    state_file = _find_state_file(file_id)
    if state_file is None:
        raise FileNotFoundError(f"Upload {file_id} not found")

    state = json.loads(state_file.read_text(encoding="utf-8"))
    if state["offset"] != offset:
        raise ValueError(f"Offset mismatch: expected {state['offset']}, got {offset}")

    file_path = _safe_staging_file_path(state["archive_name"], state["relative_path"])
    with open(file_path, "r+b") as f:
        f.seek(offset)
        f.write(data)

    new_offset = offset + len(data)
    state["offset"] = new_offset
    state_file.write_text(json.dumps(state), encoding="utf-8")
    return new_offset


def delete_upload(file_id: str):
    """Cancel an in-progress upload and delete its staging file."""
    state_file = _find_state_file(file_id)
    if state_file is None:
        return
    state = json.loads(state_file.read_text(encoding="utf-8"))
    file_path = _safe_staging_file_path(state["archive_name"], state["relative_path"])
    if file_path.exists():
        file_path.unlink()
    state_file.unlink()


def verify_archive(archive_name: str) -> dict:
    """Verify every uploaded file in the archive against its client-declared SHA-256.

    The hash is read from each TUS state JSON (stored at upload-creation time).
    Files uploaded without a declared hash are treated as passing (no-op check).
    """
    staging = get_staging_dir()
    state_dir = staging / archive_name / _TUS_STATE_DIR

    if not state_dir.exists():
        return {"status": "no_uploads", "results": []}

    results = []
    all_pass = True

    for state_file in state_dir.glob("*.json"):
        state = json.loads(state_file.read_text(encoding="utf-8"))
        rel_path = state["relative_path"]
        expected_hash = state.get("file_hash")

        # Skip integrity check for files uploaded without a declared hash
        if not expected_hash:
            results.append({"path": rel_path, "status": "no_hash"})
            continue

        try:
            file_path = _safe_staging_file_path(archive_name, rel_path)
        except ValueError:
            results.append({"path": rel_path, "status": "invalid_path"})
            all_pass = False
            continue

        if not file_path.exists():
            results.append({"path": rel_path, "status": "missing"})
            all_pass = False
            continue

        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)

        actual = sha256.hexdigest()
        ok = actual == expected_hash.lower()
        results.append({"path": rel_path, "status": "pass" if ok else "fail"})
        if not ok:
            all_pass = False
            logger.warning(
                f"Hash mismatch for {archive_name}/{rel_path}: "
                f"expected={expected_hash} actual={actual}"
            )

    if not results:
        return {"status": "no_uploads", "results": []}

    return {"status": "pass" if all_pass else "fail", "results": results}


def _collect_tus_records(archive_name: str) -> list[dict]:
    """Read all TUS state JSONs and return per-file records (path, hash, size)."""
    state_dir = get_staging_dir() / archive_name / _TUS_STATE_DIR
    records = []
    if state_dir.exists():
        for state_file in state_dir.glob("*.json"):
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
                records.append({
                    "relative_path": state["relative_path"],
                    "sha256": state.get("file_hash"),
                    "size_bytes": state.get("upload_length"),
                })
            except Exception:
                pass
    return sorted(records, key=lambda r: r["relative_path"])


def commit_archive(archive_name: str, uploader_info: dict):
    """Move a verified archive from staging to the archives directory,
    then write chain-of-custody checksum and metadata files."""
    staging = get_staging_dir()
    src = staging / archive_name
    dst = Path("archives") / archive_name

    # Collect records from TUS state files BEFORE they are deleted
    file_records = _collect_tus_records(archive_name)
    completed_at = datetime.now(timezone.utc)
    timestamp_label = completed_at.strftime("%Y%m%d_%H%M%S")

    def ts(dt: datetime) -> dict:
        """Return a timestamp block with ISO-8601 (UTC, Z suffix) and Unix epoch."""
        return {
            "iso": dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            "unix_epoch": dt.timestamp(),
            "timezone": "UTC",
        }

    tus_state = src / _TUS_STATE_DIR
    if tus_state.exists():
        shutil.rmtree(tus_state)

    os.rename(src, dst)

    # --- Checksum record ---
    checksum_doc = {
        "archive": archive_name,
        "generated_at": ts(completed_at),
        "checksum_algorithm": "SHA-256",
        "files": file_records,
    }
    (dst / f"browsing_platform_upload_checksum_{timestamp_label}.json").write_text(
        json.dumps(checksum_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # --- Upload metadata record ---
    metadata_doc = {
        "archive": archive_name,
        "upload_completed_at": ts(completed_at),
        "uploader": uploader_info,
        "server": {
            "hostname": socket.getfqdn(),
            "software": "browsing_platform",
        },
        "upload_stats": {
            "file_count": len(file_records),
            "total_bytes": sum(r["size_bytes"] or 0 for r in file_records),
            "checksum_algorithm": "SHA-256",
            "checksum_file": f"browsing_platform_upload_checksum_{timestamp_label}.json",
        },
    }
    (dst / f"browsing_platform_upload_metadata_{timestamp_label}.json").write_text(
        json.dumps(metadata_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    logger.info(f"Committed archive '{archive_name}' to archives/ with chain-of-custody records")


def cleanup_staging_archive(archive_name: str):
    """Delete a staging archive (cancel / discard)."""
    staging = get_staging_dir()
    archive_dir = staging / archive_name
    if archive_dir.exists():
        shutil.rmtree(archive_dir)
        logger.info(f"Cleaned up staging for archive '{archive_name}'")
