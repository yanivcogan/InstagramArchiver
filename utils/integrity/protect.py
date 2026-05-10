"""
High-level "protect_file" orchestration.

protect_file(path) produces, for one asset:
  - <path>.manifest.json                (chunked SHA-256 manifest, deterministic JSON)
  - <path>.manifest.json.ots            (OpenTimestamps proof of the manifest)
  - <path>.par2 / <path>.vol*.par2      (PAR2 recovery files, ~10% redundancy by default)

The manifest's SHA-256 commits to the whole-file SHA-256, every chunk hash, and
the PAR2 index hash, so a single OTS proof anchors all of them at archive time.
"""

import traceback
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from utils.integrity.chunk_manifest import (
    DEFAULT_CHUNK_SIZE,
    build_manifest,
    serialize_manifest,
    write_manifest,
)
from utils.integrity import par2 as par2_mod
from utils.opentimestamps.timestamper_opentimestamps import timestamp_file


class FileIntegrity(BaseModel):
    """Compact integrity record stored in archive metadata.

    The manifest sidecar holds the per-chunk hashes and Merkle root; this record
    just points to it and carries the load-bearing whole-file SHA-256.
    """

    algorithm: str = "sha256"
    whole_file_hash: str
    manifest_path: str
    manifest_hash: str
    par2_index_path: Optional[str] = None


class ProtectionResult(BaseModel):
    asset_path: Path
    manifest_path: Path
    manifest_hash: str
    whole_file_hash: str
    ots_path: Optional[Path] = None
    par2_paths: list[Path] = []

    def to_integrity(self, base_dir: Optional[Path] = None) -> FileIntegrity:
        def rel(p: Optional[Path]) -> Optional[str]:
            if p is None:
                return None
            if base_dir is None:
                return str(p)
            try:
                return str(Path(p).resolve().relative_to(Path(base_dir).resolve()))
            except ValueError:
                return str(p)

        index_candidate = par2_mod.index_file_for(self.asset_path)
        index_path: Optional[Path] = index_candidate if index_candidate in self.par2_paths else None

        return FileIntegrity(
            algorithm="sha256",
            whole_file_hash=self.whole_file_hash,
            manifest_path=rel(self.manifest_path) or "",
            manifest_hash=self.manifest_hash,
            par2_index_path=rel(index_path),
        )


def protect_file(
    path: Path,
    *,
    redundancy_pct: int = par2_mod.DEFAULT_REDUNDANCY_PCT,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    timestamp: bool = False,
) -> ProtectionResult:
    """
    Protect a single file end-to-end.

    Default `timestamp=False`: per-asset OTS is no longer the default — instead,
    callers should run `utils.integrity.seal_archive()` once at the end of
    archiving, which writes a single `manifests.json` listing every per-asset
    manifest hash and OTS-stamps that one file. Pass `timestamp=True` only for
    standalone uses where there is no enclosing archive seal.

    All sub-steps are best-effort: PAR2 failures and OTS failures are logged but
    do not raise, since archiving must always finish writing metadata even if a
    secondary tool is missing. The chunk manifest itself is mandatory; if its
    creation fails the exception propagates.
    """
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Cannot protect missing file: {path}")

    par2_paths: list[Path] = []
    par2_record: Optional[dict] = None
    try:
        par2_paths = par2_mod.create_recovery(path, redundancy_pct=redundancy_pct)
        index_path = par2_mod.index_file_for(path)
        if index_path.exists():
            par2_record = {
                "redundancy_pct": int(redundancy_pct),
                "index_sha256": par2_mod.hash_par2_index(index_path),
                "files": sorted(p.name for p in par2_paths),
            }
    except Exception as e:
        traceback.print_exc()
        print(f"⚠️  PAR2 recovery generation failed for {path.name}: {e}")

    manifest = build_manifest(path, chunk_size=chunk_size, par2=par2_record)
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    manifest_hash = write_manifest(manifest, manifest_path)

    ots_path: Optional[Path] = None
    if timestamp:
        try:
            ots_path = timestamp_file(manifest_path)
        except Exception as e:
            traceback.print_exc()
            print(f"⚠️  OpenTimestamps stamping failed for {manifest_path.name}: {e}")

    return ProtectionResult(
        asset_path=path,
        manifest_path=manifest_path,
        manifest_hash=manifest_hash,
        whole_file_hash=manifest["whole_file_sha256"],
        ots_path=ots_path,
        par2_paths=par2_paths,
    )
