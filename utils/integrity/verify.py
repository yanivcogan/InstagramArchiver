"""
Verification CLI / library for integrity-protected files.

Given a manifest (or an asset that has a `<asset>.manifest.json` sidecar), this
module checks:
  1. Whole-file SHA-256 matches the manifest.
  2. If not, runs PAR2 verify; if repairable, attempts repair and re-checks.
  3. Reports per-chunk pass/fail so the caller can identify which chunks remain
     provably original even when others are corrupted.

OpenTimestamps verification of the manifest itself is delegated to the existing
`utils.opentimestamps.timestamper_opentimestamps.verify_timestamp`.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from utils.integrity.chunk_manifest import (
    ChunkVerifyReport,
    read_manifest,
    verify_against_manifest,
)
from utils.integrity import par2 as par2_mod


class VerifyReport(BaseModel):
    asset_path: Path
    manifest_path: Path
    manifest_hash_ok: bool
    chunk_report: ChunkVerifyReport
    par2_repaired: bool = False
    final_whole_file_ok: bool


def _resolve_manifest(target: Path) -> Path:
    target = Path(target)
    if target.suffix == ".json" and target.name.endswith(".manifest.json"):
        return target
    candidate = target.with_suffix(target.suffix + ".manifest.json")
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"No manifest found next to {target} (looked for {candidate})")


def _resolve_asset(manifest_path: Path) -> Path:
    name = manifest_path.name
    if not name.endswith(".manifest.json"):
        raise ValueError(f"Manifest filename must end in .manifest.json: {manifest_path}")
    asset_name = name[: -len(".manifest.json")]
    return manifest_path.with_name(asset_name)


def verify_protected_file(target: Path, *, attempt_repair: bool = True) -> VerifyReport:
    manifest_path = _resolve_manifest(target)
    asset_path = _resolve_asset(manifest_path)

    manifest = read_manifest(manifest_path)
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    expected_manifest_hash = manifest.get("_manifest_hash_self_check")
    manifest_hash_ok = expected_manifest_hash in (None, manifest_hash)

    report = verify_against_manifest(asset_path, manifest)

    par2_repaired = False
    if not report.whole_file_ok and attempt_repair:
        index_path = par2_mod.index_file_for(asset_path)
        if index_path.exists():
            try:
                if par2_mod.repair(index_path):
                    par2_repaired = True
                    report = verify_against_manifest(asset_path, manifest)
            except Exception:
                pass

    return VerifyReport(
        asset_path=asset_path,
        manifest_path=manifest_path,
        manifest_hash_ok=manifest_hash_ok,
        chunk_report=report,
        par2_repaired=par2_repaired,
        final_whole_file_ok=report.whole_file_ok,
    )


def _verify_archive_dir(archive_dir: Path, *, attempt_repair: bool) -> int:
    manifests = sorted(archive_dir.rglob("*.manifest.json"))
    if not manifests:
        print(f"No manifests found under {archive_dir}")
        return 1
    failures = 0
    for m in manifests:
        try:
            r = verify_protected_file(m, attempt_repair=attempt_repair)
        except Exception as e:
            print(f"❌ {m.relative_to(archive_dir)}: {e}")
            failures += 1
            continue
        status = "✅" if r.final_whole_file_ok else "❌"
        repaired = " (par2-repaired)" if r.par2_repaired else ""
        bad = r.chunk_report.bad_chunk_indices
        bad_summary = "" if not bad else f" — {len(bad)} bad chunk(s) at {bad[:8]}{'...' if len(bad) > 8 else ''}"
        print(f"{status} {r.asset_path.relative_to(archive_dir)}{repaired}{bad_summary}")
        if not r.final_whole_file_ok:
            failures += 1
    return 0 if failures == 0 else 2


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify integrity-protected archive files.")
    parser.add_argument("target", type=Path, help="Archive directory or specific .manifest.json / asset file.")
    parser.add_argument("--no-repair", action="store_true", help="Skip PAR2 repair attempts on failure.")
    args = parser.parse_args()

    target: Path = args.target.resolve()
    attempt_repair = not args.no_repair

    if target.is_dir():
        sys.exit(_verify_archive_dir(target, attempt_repair=attempt_repair))

    report = verify_protected_file(target, attempt_repair=attempt_repair)
    print(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
    sys.exit(0 if report.final_whole_file_ok else 2)


if __name__ == "__main__":
    main()
