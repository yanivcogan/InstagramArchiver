"""
V021 — Re-extract broken partial-stream video files

The video extraction algorithm before commit 2c2ce9a assembled DASH byte-range
segments without detecting gaps in coverage. When a video was only partially
streamed, the resulting fMP4 file contained a truncated mdat whose declared
size exceeded the bytes actually available, making the file unplayable.

This migration:
  1. Scans all media_archive rows that reference a .mp4 local_url (in batches
     of 1,000 to avoid loading the full table into memory)
  2. Checks each file for the specific corruption signature: an mdat box whose
     declared size exceeds the remaining file bytes (pure-Python, no ffmpeg)
  3. For each broken file, moves it to a _broken_videos/ subdirectory (preserves
     it for rollback), then re-runs the HAR-based extraction for that video
  4. Updates media_archive.local_url if the new file has a different name
  5. Resets incorporation_status to 'pending' for every affected archive session
     so entity extraction re-runs with the fixed files on the next full pipeline run
  6. Resets thumbnail_status / thumbnail_path for every affected canonical media
     entry so thumbnails regenerate from the fixed files
"""

import os
import struct
from collections import defaultdict
from pathlib import Path
from typing import Optional

from db_loaders.db_intake import LOCAL_ARCHIVES_DIR_ALIAS
from extractors.extract_videos import extract_video_maps, save_fetched_asset
from root_anchor import ROOT_ARCHIVES


SCAN_BATCH = 1_000   # rows per page when scanning media_archive


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_fmp4_truncated(file_path: Path) -> bool:
    """
    Return True if any mdat box in the file is truncated (declared size > remaining
    bytes). Reads only box headers (8-16 bytes each), never the media payload.
    """
    try:
        file_size = file_path.stat().st_size
        if file_size < 8:
            return False
        with open(file_path, 'rb') as f:
            pos = 0
            while pos + 8 <= file_size:
                f.seek(pos)
                header = f.read(8)
                if len(header) < 8:
                    break
                size = struct.unpack_from('>I', header, 0)[0]
                btype = header[4:8].decode('latin-1', errors='replace')

                if size == 0:
                    # Box extends to end of file — valid by definition
                    break
                if size == 1:
                    # 64-bit extended size
                    ext = f.read(8)
                    if len(ext) < 8:
                        return True  # truncated extended-size field
                    size = struct.unpack_from('>Q', ext, 0)[0]
                if size < 8:
                    break

                if btype == 'mdat':
                    if pos + size > file_size:
                        return True  # mdat extends beyond EOF

                pos += size
        return False
    except Exception:
        return False


def _resolve_local_url(local_url: str) -> Optional[Path]:
    """Resolve an alias-format local_url to an absolute Path."""
    parts = local_url.split("/", 1)
    if len(parts) < 2:
        return None
    return ROOT_ARCHIVES / parts[1]


def _extract_asset_id(filename: str) -> Optional[str]:
    """
    Extract the xpv_asset_id from a video filename.
    Handles: xpv_{id}.mp4, xpv_{id}_full.mp4, track_{id}_{name}_{type}.mp4
    """
    try:
        asset_id = filename
        asset_id = asset_id.split('track_')[1] if 'track_' in asset_id else asset_id
        asset_id = asset_id.split('xpv_')[1] if 'xpv_' in asset_id else asset_id
        asset_id = asset_id.split('_')[0] if '_' in asset_id else asset_id
        asset_id = asset_id.split('.mp4')[0] if '.mp4' in asset_id else asset_id
        return asset_id if asset_id else None
    except (IndexError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------

def run(cnx):
    cur = cnx.cursor()
    try:
        # ------------------------------------------------------------------ #
        # Step 1: Scan media_archive in batches, detect broken files
        # ------------------------------------------------------------------ #
        # broken_by_session: session_id -> [(ma_id, local_url, archive_location, asset_id, canonical_id)]
        broken_by_session: dict[int, list] = defaultdict(list)
        offset = 0
        total_scanned = 0

        while True:
            cur.execute(
                """SELECT ma.id, ma.local_url, ma.archive_session_id,
                          s.archive_location, ma.canonical_id
                   FROM media_archive ma
                   JOIN archive_session s ON s.id = ma.archive_session_id
                   WHERE ma.local_url IS NOT NULL
                     AND ma.local_url LIKE '%.mp4%'
                     AND s.source_type = 'local_har'
                   ORDER BY ma.id
                   LIMIT %s OFFSET %s""",
                (SCAN_BATCH, offset),
            )
            rows = cur.fetchall()
            if not rows:
                break

            for ma_id, local_url, session_id, archive_location, canonical_id in rows:
                file_path = _resolve_local_url(local_url)
                if file_path is None or not file_path.exists():
                    continue
                if _is_fmp4_truncated(file_path):
                    asset_id = _extract_asset_id(file_path.name)
                    if asset_id:
                        broken_by_session[session_id].append(
                            (ma_id, local_url, archive_location, asset_id, canonical_id)
                        )

            total_scanned += len(rows)
            print(f"    V021: scanned {total_scanned} entries so far …")
            offset += SCAN_BATCH

        total_broken = sum(len(v) for v in broken_by_session.values())
        print(f"    V021: scanned {total_scanned} total entries; "
              f"found {total_broken} broken video file(s) across "
              f"{len(broken_by_session)} archive session(s)")

        if not broken_by_session:
            print("    V021: nothing to do")
            return

        # ------------------------------------------------------------------ #
        # Step 2: Per session — parse HAR once, re-extract broken videos
        # ------------------------------------------------------------------ #
        fixed_count = 0
        skipped_count = 0
        affected_session_ids: set[int] = set()
        affected_canonical_ids: set[int] = set()

        for session_id, broken_entries in broken_by_session.items():
            # All entries in this session share the same archive_location
            archive_location = broken_entries[0][2]
            archive_location_parts = archive_location.split("/", 1)
            if len(archive_location_parts) < 2:
                print(f"    V021: [session {session_id}] cannot parse archive_location={archive_location!r}, skipping")
                skipped_count += len(broken_entries)
                continue

            archive_dir = ROOT_ARCHIVES / archive_location_parts[1]
            har_path = archive_dir / "archive.har"
            if not har_path.exists():
                print(f"    V021: [session {session_id}] HAR not found at {har_path}, skipping")
                skipped_count += len(broken_entries)
                continue

            print(f"    V021: [session {session_id}] parsing HAR {archive_dir.name} …")
            try:
                har_videos = extract_video_maps(har_path)
            except Exception as e:
                print(f"    V021: [session {session_id}] extract_video_maps failed: {e}, skipping")
                skipped_count += len(broken_entries)
                continue

            video_by_asset_id = {v.xpv_asset_id: v for v in har_videos}
            broken_dir = archive_dir / "_broken_videos"

            for ma_id, local_url, _, asset_id, canonical_id in broken_entries:
                video = video_by_asset_id.get(asset_id)
                if video is None:
                    print(f"    V021: asset {asset_id} not found in HAR (may have been a full download), skipping")
                    skipped_count += 1
                    continue

                # Move ALL files in the archive dir that belong to this asset
                # (xpv_*.mp4 and track_*.mp4) so that save_fetched_asset
                # does not skip them as "already existing".
                broken_dir.mkdir(exist_ok=True)
                for candidate in list(archive_dir.iterdir()):
                    if candidate.is_file() and _extract_asset_id(candidate.name) == asset_id:
                        dest = broken_dir / candidate.name
                        if dest.exists():
                            dest = broken_dir / (candidate.stem + "_dup" + candidate.suffix)
                        os.rename(candidate, dest)
                        print(f"    V021: preserved broken file → _broken_videos/{candidate.name}")

                # Re-extract
                try:
                    result = save_fetched_asset(video, archive_dir, download_full_track=False)
                except Exception as e:
                    print(f"    V021: save_fetched_asset failed for asset {asset_id}: {e}")
                    skipped_count += 1
                    continue

                if not result.success or result.location is None:
                    print(f"    V021: re-extraction produced no output for asset {asset_id}")
                    skipped_count += 1
                    continue

                # Build new alias-format local_url
                new_local_url = (
                    f"{LOCAL_ARCHIVES_DIR_ALIAS}/"
                    + result.location.relative_to(ROOT_ARCHIVES).as_posix()
                )

                if new_local_url != local_url:
                    cur.execute(
                        "UPDATE media_archive SET local_url = %s WHERE id = %s",
                        (new_local_url, ma_id),
                    )
                    print(f"    V021: updated media_archive {ma_id}: {local_url} → {new_local_url}")

                affected_session_ids.add(session_id)
                affected_canonical_ids.add(canonical_id)
                fixed_count += 1

            # Commit after each session so progress survives partial failures
            cnx.commit()

        print(f"    V021: re-extraction done — fixed {fixed_count}, skipped {skipped_count}")

        # ------------------------------------------------------------------ #
        # Step 3: Reset incorporation_status for affected archive sessions
        # ------------------------------------------------------------------ #
        if affected_session_ids:
            ph = ','.join(['%s'] * len(affected_session_ids))
            cur.execute(
                f"UPDATE archive_session SET incorporation_status = 'pending' WHERE id IN ({ph})",
                list(affected_session_ids),
            )
            cnx.commit()
            print(f"    V021: reset incorporation_status to 'pending' for {cur.rowcount} session(s)")

        # ------------------------------------------------------------------ #
        # Step 4: Reset thumbnail status for affected canonical media entries
        # ------------------------------------------------------------------ #
        if affected_canonical_ids:
            ph = ','.join(['%s'] * len(affected_canonical_ids))
            cur.execute(
                f"""UPDATE media
                    SET thumbnail_status = 'pending', thumbnail_path = NULL
                    WHERE id IN ({ph})""",
                list(affected_canonical_ids),
            )
            cnx.commit()
            print(f"    V021: reset thumbnail_status to 'pending' for {cur.rowcount} media entry/entries")

        print("    V021: done")

    finally:
        cur.close()
