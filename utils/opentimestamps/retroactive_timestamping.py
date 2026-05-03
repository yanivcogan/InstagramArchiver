"""
retroactive_timestamping.py

Scans all archives and creates OpenTimestamps (.ots) proofs for any hash files
that are missing them. Useful when archiving sessions ran before timestamping
was set up, or when timestamping failed mid-session.

Files timestamped per archive (if they exist and have no .ots sibling):
  - **/*.manifest.json  (current scheme: chunked SHA-256 + PAR2 manifests)
  - har_hash.txt, fuzzy_har_hash.txt, photos/photo_*hashes_hash_*.txt,
    videos/full_track_*hashes_hash_*.txt  (legacy schemes, kept harmless;
    new archives won't produce these)

Usage:
    uv run python utils/opentimestamps/retroactive_timestamping.py
"""

from pathlib import Path

from root_anchor import ROOT_DIR
from utils.opentimestamps.timestamper_opentimestamps import timestamp_file

ARCHIVES_DIR = Path(ROOT_DIR) / "archives"

# Glob patterns (relative to each archive directory) for files that should be timestamped.
HASH_FILE_PATTERNS = [
    # Current scheme — chunked-hash + PAR2 manifests anywhere in the archive.
    "**/*.manifest.json",
    # Legacy schemes — preserved so re-running this tool on old archives still works.
    "har_hash.txt",
    "fuzzy_har_hash.txt",
    "photos/photo_hashes_hash_*.txt",
    "photos/photo_fuzzy_hashes_hash_*.txt",
    "videos/full_track_hashes_hash_*.txt",
    "videos/full_track_fuzzy_hashes_hash_*.txt",
]


def stamp_archive(archive_dir: Path) -> list[Path]:
    """
    Timestamps any hash files in archive_dir that are missing a .ots proof.
    Returns the list of files that were successfully timestamped.
    """
    stamped = []

    candidates = []
    for pattern in HASH_FILE_PATTERNS:
        candidates.extend(archive_dir.glob(pattern))

    for hash_file in sorted(candidates):
        ots_file = hash_file.with_suffix(hash_file.suffix + ".ots")
        if ots_file.exists():
            continue

        print(f"  Stamping {hash_file.relative_to(archive_dir)} ...", end=" ", flush=True)
        try:
            timestamp_file(hash_file)
            print("done")
            stamped.append(hash_file)
        except Exception as e:
            print(f"FAILED: {e}")

    return stamped


def stamp_all_archives(archives_dir: Path = ARCHIVES_DIR) -> None:
    """
    Iterates over every subdirectory in archives_dir and timestamps any
    hash files that are missing .ots proofs.
    """
    archive_dirs = sorted(
        (d for d in archives_dir.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_ctime,
        reverse=True,
    )

    if not archive_dirs:
        print(f"No archives found in {archives_dir}")
        return

    total_stamped = 0

    for archive_dir in archive_dirs:
        stamped = stamp_archive(archive_dir)
        if stamped:
            print(f"[{archive_dir.name}] Timestamped {len(stamped)} file(s).")
            total_stamped += len(stamped)
        else:
            print(f"[{archive_dir.name}] All hash files already timestamped (or none present).")

    print(f"\nDone. Total files timestamped: {total_stamped}")


if __name__ == "__main__":
    stamp_all_archives()
