"""
WACZ Metadata Extractor
=======================

Reads all available metadata from a WACZ (Web Archive Collection Zipped) file
and returns a single comprehensive dict suitable for storing as metadata.json
or in the archive_session.metadata database column.

Sources:
  - datapackage.json         : title, timestamps, software, resource hashes
  - datapackage-digest.json  : ECDSA digital signature for authenticity
  - pages/pages.jsonl        : full page-visit timeline with URLs and titles
  - indexes/index.cdx[.gz]   : per-resource capture stats (MIME, timestamps)
"""

import gzip
import json
import zipfile
from pathlib import Path
from typing import Optional


def extract_wacz_metadata(wacz_path: Path) -> dict:
    """
    Open a WACZ file and extract all available metadata.

    Returns a dict with the following top-level keys:
      source, wacz_filename,
      title, created, modified, wacz_version, software, resources,
      datapackage_hash, signature,
      pages, total_pages_visited,
      capture_stats,
      primary_instagram_url, primary_instagram_username,
      archive_size_bytes
    """
    metadata: dict = {
        "source": "wacz",
        "wacz_filename": wacz_path.name,
    }

    with zipfile.ZipFile(wacz_path, "r") as zf:
        names = set(zf.namelist())

        # ------------------------------------------------------------------ #
        # datapackage.json
        # ------------------------------------------------------------------ #
        if "datapackage.json" in names:
            try:
                dp = json.loads(zf.read("datapackage.json"))
                metadata["title"] = dp.get("title")
                metadata["created"] = dp.get("created")
                metadata["modified"] = dp.get("modified")
                metadata["wacz_version"] = dp.get("wacz_version")
                metadata["software"] = dp.get("software")
                metadata["resources"] = dp.get("resources", [])
            except Exception as e:
                print(f"[wacz_metadata] Error reading datapackage.json: {e}")

        # ------------------------------------------------------------------ #
        # datapackage-digest.json  (Webrecorder ≥ 0.11)
        # ------------------------------------------------------------------ #
        if "datapackage-digest.json" in names:
            try:
                digest = json.loads(zf.read("datapackage-digest.json"))
                metadata["datapackage_hash"] = digest.get("hash")
                signed = digest.get("signedData", {}) or {}
                if signed:
                    metadata["signature"] = {
                        "hash": signed.get("hash"),
                        "signature": signed.get("signature"),
                        "public_key": signed.get("publicKey"),
                        "created": signed.get("created"),
                        "software": signed.get("software"),
                    }
            except Exception as e:
                print(f"[wacz_metadata] Error reading datapackage-digest.json: {e}")

        # ------------------------------------------------------------------ #
        # pages/pages.jsonl
        # ------------------------------------------------------------------ #
        pages = []
        if "pages/pages.jsonl" in names:
            try:
                raw = zf.read("pages/pages.jsonl").decode("utf-8", errors="replace")
                for line in raw.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        # Skip the JSONL header descriptor line
                        if obj.get("format") == "json-pages-1.0":
                            continue
                        pages.append({
                            "url": obj.get("url"),
                            "title": obj.get("title"),
                            "ts": obj.get("ts"),
                            "id": obj.get("id"),
                            "size": obj.get("size"),
                            "favicon_url": obj.get("favIconUrl"),
                            # Keep a short excerpt; full text can be very large
                            "text_excerpt": (obj.get("text") or "")[:500],
                        })
                    except Exception:
                        pass
            except Exception as e:
                print(f"[wacz_metadata] Error reading pages/pages.jsonl: {e}")
        metadata["pages"] = pages
        metadata["total_pages_visited"] = len(pages)

        # ------------------------------------------------------------------ #
        # CDX index  (indexes/index.cdx.gz preferred, fall back to .cdx)
        # ------------------------------------------------------------------ #
        capture_stats: dict = {
            "total_captures": 0,
            "mime_breakdown": {},
            "capture_timespan": {"first": None, "last": None},
            "unique_urls": 0,
        }
        cdx_name: Optional[str] = None
        cdx_compressed = False
        if "indexes/index.cdx.gz" in names:
            cdx_name = "indexes/index.cdx.gz"
            cdx_compressed = True
        elif "indexes/index.cdx" in names:
            cdx_name = "indexes/index.cdx"

        if cdx_name:
            try:
                raw_cdx = zf.read(cdx_name)
                if cdx_compressed:
                    raw_cdx = gzip.decompress(raw_cdx)

                unique_urls: set = set()
                ts_list: list = []
                mime_breakdown: dict = {}
                count = 0

                for line in raw_cdx.decode("utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if not line or line.startswith("!"):
                        continue
                    parts = line.split("\t", 2)
                    if len(parts) < 3:
                        continue
                    ts_str = parts[1]
                    try:
                        entry = json.loads(parts[2])
                    except Exception:
                        continue

                    mime = entry.get("mime") or ""
                    url = entry.get("url") or ""

                    if mime:
                        mime_breakdown[mime] = mime_breakdown.get(mime, 0) + 1
                    if url:
                        unique_urls.add(url)
                    if ts_str:
                        ts_list.append(ts_str)
                    count += 1

                capture_stats["total_captures"] = count
                capture_stats["mime_breakdown"] = mime_breakdown
                capture_stats["unique_urls"] = len(unique_urls)
                if ts_list:
                    capture_stats["capture_timespan"] = {
                        "first": min(ts_list),
                        "last": max(ts_list),
                    }
            except Exception as e:
                print(f"[wacz_metadata] Error parsing CDX index: {e}")

        metadata["capture_stats"] = capture_stats

    # ---------------------------------------------------------------------- #
    # Derived fields (computed from data already collected above)
    # ---------------------------------------------------------------------- #

    # Primary URL: URL of the first page in the archive
    metadata["primary_url"] = pages[0]["url"] if pages else None

    # Archive size: sum of declared resource sizes from datapackage
    resources = metadata.get("resources") or []
    metadata["archive_size_bytes"] = sum(
        r.get("bytes", 0) for r in resources if isinstance(r, dict)
    )

    return metadata
