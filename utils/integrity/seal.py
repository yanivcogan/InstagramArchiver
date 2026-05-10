"""
Single archive-level seal: one manifests.json (with OTS proof) covering every
per-asset manifest in an archive directory.

The summary commits to the SHA-256 of every `*.manifest.json` in the tree, so a
single OTS proof on `manifests.json` anchors all chunk hashes, all whole-file
hashes, and every PAR2 index hash transitively. Per-asset .ots files are no
longer needed.

Verification chain:
  asset bytes  --SHA-256-->  per-asset manifest
  per-asset manifest  --SHA-256-->  manifests.json entry
  manifests.json  --OTS-->  blockchain timestamp
"""

import datetime
import hashlib
import json
import traceback
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from utils.opentimestamps.timestamper_opentimestamps import timestamp_file

SEAL_FILENAME = "manifests.json"


def _merkle_root_hex(hexes: list[str]) -> str:
    if not hexes:
        return hashlib.sha256(b"").hexdigest()
    layer = [bytes.fromhex(h) for h in hexes]
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [
            hashlib.sha256(layer[i] + layer[i + 1]).digest()
            for i in range(0, len(layer), 2)
        ]
    return layer[0].hex()


class SealResult(BaseModel):
    summary_path: Path
    summary_hash: str
    ots_path: Optional[Path] = None
    manifest_count: int
    merkle_root: str


def seal_archive(archive_dir: Path, summary_name: str = SEAL_FILENAME) -> SealResult:
    """
    Walk `archive_dir` recursively, hash every `*.manifest.json`, write a single
    summary file, and OpenTimestamp it. Returns a `SealResult` even if OTS
    stamping fails (ots_path will be None in that case).
    """
    archive_dir = Path(archive_dir).resolve()
    summary_path = archive_dir / summary_name

    manifests = sorted(
        p for p in archive_dir.rglob("*.manifest.json") if p.name != summary_name
    )

    entries = []
    chunk_hash_inputs: list[str] = []
    for mp in manifests:
        data = mp.read_bytes()
        manifest_sha256 = hashlib.sha256(data).hexdigest()
        entries.append(
            {
                "path": mp.relative_to(archive_dir).as_posix(),
                "manifest_sha256": manifest_sha256,
            }
        )
        chunk_hash_inputs.append(manifest_sha256)

    merkle_root = _merkle_root_hex(chunk_hash_inputs)
    summary = {
        "version": 1,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "algorithm": "sha256",
        "manifest_count": len(entries),
        "merkle_root": merkle_root,
        "manifests": entries,
    }

    payload = json.dumps(summary, sort_keys=True, separators=(",", ":")).encode("utf-8")
    summary_path.write_bytes(payload)
    summary_hash = hashlib.sha256(payload).hexdigest()

    ots_path: Optional[Path] = None
    try:
        ots_path = timestamp_file(summary_path)
    except Exception as e:
        traceback.print_exc()
        print(f"⚠️  OpenTimestamps stamping failed for {summary_path.name}: {e}")

    return SealResult(
        summary_path=summary_path,
        summary_hash=summary_hash,
        ots_path=ots_path,
        manifest_count=len(entries),
        merkle_root=merkle_root,
    )
