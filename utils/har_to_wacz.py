"""
HAR -> replayable WACZ converter.

Why this exists (and why we don't just reuse archiveweb.page):
``har2warc`` -- and wabac.js's own ``HARLoader`` -- write each HAR entry as an
independent record. Instagram/Threads stream video as many HTTP **206 partial**
responses (byte ranges of one file), so those tools emit a pile of fragments that
will not play back on replayweb.page. archiveweb.page avoids this not by stitching
the partials it captured, but by **re-fetching the full resource live without a
Range header** (``recorder.ts`` discards every 206) and slicing that stored full
buffer at replay time. From a *static* HAR we cannot re-fetch, so this converter
does the merge itself: it groups a resource's 206 partials by URL, splices them
into one full byte array, and emits a single status-200 WARC record. wabac.js then
manufactures the per-request 206 ranges at replay time from that full resource.

The merged record is stored under the **whole-file URL** (the captured URL minus the
``bytestart``/``byteend`` range params, signing query kept) -- NOT a query-stripped
key. wabac matches media by a generic rule that prefix-scans the CDX over
``[".../f.mp4?", ".../f.mp4@")`` before reducing both sides to the path; a
query-stripped key (``.../f.mp4``) sorts below that range and is never found (404),
while a key that keeps its ``?query`` lands inside it. See ``_whole_file_url``.

Everything else (HTML/JS/CSS/JSON/images) is written faithfully, one record per
entry, decoded (Playwright stores decoded bodies) with Content-Encoding normalised
to identity so the stored headers match the stored bytes.

Range parsing is shared with the ingestion pipeline via
``extractors/extract_videos.py`` (Threads puts the range in the response
``Content-Range``; Instagram puts ``bytestart``/``byteend`` in the URL query).

Packaging is done by **js-wacz** (Node), NOT py-wacz. replayweb.page/wabac
recomputes the CDX lookup key at replay time with warcio.js (``getSurt`` keeps a
path's trailing slash; ``postToGetUrl`` appends the POST body after ``decodeURI``,
which leaves reserved chars like ``%2f`` encoded). py-wacz uses Python ``surt``
(strips the trailing slash) and ``cdxj_indexer`` (``unquote_plus`` fully decodes the
body), so its POST keys never match wabac's -- POST/GraphQL fetches silently 404 at
replay and dynamic pages don't work. js-wacz uses the same warcio.js code as the
replayer, so keys match. See ``utils/wacz_packager/``.

Instagram batches route prefetches into large multi-route
``/ajax/bulk-route-definitions/`` POSTs at capture, but issues many SINGLE-route
requests at replay (different timing). wabac has no Instagram fuzzy rule, so its
generic query-prefix matcher scores by overall URL similarity and serves a
single-route request the WRONG batch -- the needed route never caches, and the app
falls back to a per-item ``/ajax/route-definition/`` that was never captured (404).
Fix: ``_bulk_route_singles`` splits each captured multi-route response into
per-route single-route records so stock wabac serves each route correctly. This
reshapes captured route-definition data into request/response pairs that weren't
literally sent -- acceptable here because the raw HAR remains the source of truth and
the WACZ is a researcher-facing view.

Usage:
    uv run utils/har_to_wacz.py path/to/archive.har [-o out.wacz] [--url PAGE_URL]
"""

import argparse
import base64
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional
from urllib.parse import parse_qsl, quote, urlsplit, urlunsplit

import ijson
from warcio.statusandheaders import StatusAndHeaders
from warcio.warcwriter import WARCWriter

# Reused, dependency-free range parsers (single source of truth with the
# ingestion pipeline). Threads/Barcelona uses standard HTTP ranges; these read
# the response Content-Range and request Range headers.
from extractors.extract_videos import (
    _header_value,
    _parse_content_range,
    _parse_range_header,
)

# Response body byte streams that arrive as HTTP 206 ranges and must be merged
# into one full resource for replay. Manifests (.m3u8/.mpd) are NOT here: they are
# small text resources written as ordinary records.
_MEDIA_EXTS = (".mp4", ".m4v", ".m4a", ".m4s", ".ts", ".aac", ".mp3", ".webm", ".mov")

# HTTP response headers that must not survive verbatim: the body we store is the
# decoded body, and we recompute Content-Length ourselves.
_DROP_HEADERS = {"content-length", "content-encoding", "transfer-encoding"}

# Instagram encodes a media byte range in the URL query under these params (Threads
# instead uses a response Content-Range header, so its URL carries no range). Single
# source of truth for both reading the range and stripping it from the stored URL.
_URL_RANGE_PARAMS = ("bytestart", "byteend")


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _decode_body(content: dict) -> bytes:
    """Decode a HAR response body. Playwright stores binary as base64 (``encoding``
    == 'base64') and text as the already-decoded string."""
    text = content.get("text")
    if text is None:
        return b""
    if content.get("encoding") == "base64":
        try:
            return base64.b64decode(text)
        except Exception:
            # Don't lose this silently -- an empty body in an evidentiary archive
            # should be visible, not mistaken for a faithful capture.
            print("[har_to_wacz] WARNING: could not base64-decode a response body; "
                  "storing it empty")
            return b""
    return text.encode("utf-8", errors="replace")


def _iso_to_warc_date(started: Optional[str]) -> Optional[str]:
    """Normalise a HAR ``startedDateTime`` to a WARC-1.0 date (UTC, no fraction)."""
    if not started:
        return None
    try:
        dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


def _content_range_total(value: Optional[str]) -> Optional[int]:
    """Total size from a ``Content-Range: bytes A-B/TOTAL`` header, if present."""
    if not value:
        return None
    m = re.search(r"/(\d+)\s*$", value)
    return int(m.group(1)) if m else None


def _url_byte_range(url: str) -> tuple[Optional[int], Optional[int]]:
    """Instagram encodes the byte range in the URL query (see ``_URL_RANGE_PARAMS``)."""
    q = dict(parse_qsl(urlsplit(url).query))
    bs, be = q.get(_URL_RANGE_PARAMS[0]), q.get(_URL_RANGE_PARAMS[1])
    if bs is not None and be is not None:
        try:
            return int(bs), int(be)
        except ValueError:
            return None, None
    return None, None


def _media_key(url: str) -> str:
    """In-memory *grouping* key for a media resource: scheme+host+path, query
    stripped. Collapses every signed-query / byte-range variant of one video onto a
    single bucket to merge. This is NOT the stored WARC-Target-URI -- see
    ``_whole_file_url`` for why the stored URL must keep its query."""
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def _whole_file_url(url: str) -> str:
    """The stored WARC-Target-URI for a merged media resource: the captured URL with
    only the byte-range params (``bytestart``/``byteend``) removed, all signing/query
    params kept.

    The query MUST be kept. At replay wabac matches media by its generic rule
    ``/(\\.(?:mp4|jpg|...))\\?.*/ -> "$1"``: it does an IndexedDB *prefix* scan over
    ``[".../file.mp4?", ".../file.mp4@")`` and only then reduces both sides to the
    query-less path to compare. A merged record stored under a *query-stripped* key
    (``.../file.mp4``, no ``?``) sorts lexicographically BELOW that range's lower
    bound, so the scan never returns it and the request 404s -- even though the bytes
    are present. Keeping a ``?query`` puts the key inside the scan range (exactly how
    faithfully-stored images and archiveweb.page's own captures already behave); the
    differing signing params don't matter because the rule strips them before
    comparing on path."""
    p = urlsplit(url)
    drop = tuple(f"{name}=" for name in _URL_RANGE_PARAMS)
    kept = [seg for seg in p.query.split("&")
            if seg and not seg.startswith(drop)]
    return urlunsplit((p.scheme, p.netloc, p.path, "&".join(kept), ""))


def _is_mergeable_media(url: str, mime: str, status: int, entry: dict) -> bool:
    """True for response byte streams that should be merged per-URL into one 200."""
    if mime.startswith("video/") or mime.startswith("audio/"):
        return True
    path = urlsplit(url).path.lower()
    if path.endswith(_MEDIA_EXTS):
        return True
    if status == 206:
        return True
    if _url_byte_range(url)[0] is not None:
        return True
    if _header_value(entry.get("request", {}).get("headers", []), "range"):
        return True
    return False


def _segment_range(entry: dict, url: str) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Return ``(start, end_inclusive, total_or_None)`` for one media segment.

    Priority: Threads response ``Content-Range`` (authoritative, carries total) ->
    Instagram URL ``bytestart``/``byteend`` -> request ``Range`` header.
    """
    resp_headers = entry.get("response", {}).get("headers", [])
    cr_val = _header_value(resp_headers, "content-range")
    s, e = _parse_content_range(cr_val)
    if s is not None:
        return s, e, _content_range_total(cr_val)

    s, e = _url_byte_range(url)
    if s is not None:
        return s, e, None

    s, e = _parse_range_header(_header_value(entry.get("request", {}).get("headers", []), "range"))
    if s is not None:
        return s, e, None

    return None, None, None


def _clean_headers(raw_headers, drop: set) -> list:
    """(name, value) tuples from HAR headers, skipping HTTP/2 pseudo-headers (``:``
    prefixed) and any header whose lowercased name is in ``drop``. Shared by the
    response and request record builders."""
    out = []
    for h in raw_headers or []:
        name = h.get("name", "")
        if not name or name.startswith(":"):  # skip HTTP/2 pseudo-headers
            continue
        if name.lower() in drop:
            continue
        out.append((name, h.get("value", "")))
    return out


def _build_http_headers(raw_headers, body_len: int, *, mime: str, drop_range: bool) -> list:
    """HTTP header tuples for the stored response: drop encoding/length (and range
    for merged media), skip HTTP/2 pseudo-headers, set our Content-Length."""
    drop = set(_DROP_HEADERS)
    if drop_range:
        drop.add("content-range")
    out = _clean_headers(raw_headers, drop)
    if mime and not any(n.lower() == "content-type" for n, _ in out):
        out.append(("Content-Type", mime))
    out.append(("Content-Length", str(body_len)))
    return out


def _assemble(segments: list, total: Optional[int]) -> tuple[bytes, list]:
    """Splice ``(start, bytes)`` segments into one buffer. Returns (data, gaps)."""
    segs = sorted(segments, key=lambda sb: sb[0])
    size = total or max((s + len(b) for s, b in segs), default=0)
    buf = bytearray(size)
    # Fill and detect coverage gaps in one pass over the sorted segments.
    gaps, cursor = [], 0
    for start, data in segs:
        end = start + len(data)
        if end > len(buf):  # a tail past the declared total: grow to fit
            buf.extend(b"\x00" * (end - len(buf)))
        if start > cursor:
            gaps.append((cursor, start))
        buf[start:end] = data
        cursor = max(cursor, end)
    if total and cursor < total:
        gaps.append((cursor, total))
    return bytes(buf), gaps


# --------------------------------------------------------------------------- #
# WARC writing
# --------------------------------------------------------------------------- #
def _build_response_record(writer, url, status, status_text, raw_headers, body, mime,
                           ts_iso, *, drop_range):
    http_headers = StatusAndHeaders(
        f"{status} {status_text}".strip(),
        _build_http_headers(raw_headers, len(body), mime=mime, drop_range=drop_range),
        protocol="HTTP/1.1",
    )
    warc_headers_dict = {"WARC-Date": ts_iso} if ts_iso else None
    return writer.create_warc_record(
        url, "response",
        payload=BytesIO(body), length=len(body),
        http_headers=http_headers, warc_headers_dict=warc_headers_dict,
    )


def _build_request_record(writer, request: dict, url: str, method: str):
    """Build a WARC ``request`` record carrying method, headers and the request
    body. This is what lets py-wacz's post_append indexer fold the POST body into
    the CDX key so wabac can match POST/GraphQL fetches at replay.

    ``cdxj_indexer`` parses the body according to the request Content-Type. Its
    ``multipart/*`` branch iterates the body with an *unguarded* MultipartParser,
    which raises and aborts the whole index when the body isn't a faithful raw
    multipart stream -- which HARs never capture (Playwright exposes multipart as
    structured ``postData.params``, not the raw boundary-delimited bytes). So for
    multipart requests we drop the Content-Type, sending cdxj_indexer down its safe
    base64 path instead. (urlencoded / json / binary bodies are all handled safely.)
    """
    parts = urlsplit(url)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query

    text = (request.get("postData") or {}).get("text")
    body = text.encode("utf-8") if text else b""

    # Drop the original Content-Length (we set our own to the captured body) and
    # content/transfer-encoding (the HAR body is already decoded). For multipart we
    # also drop Content-Type (see docstring: routes cdxj_indexer to its safe path).
    ctype = (_header_value(request.get("headers", []), "content-type") or "").lower()
    drop = set(_DROP_HEADERS)
    if ctype.startswith("multipart/"):
        drop.add("content-type")

    headers = _clean_headers(request.get("headers"), drop)
    if not any(n.lower() == "host" for n, _ in headers):
        headers.append(("Host", parts.netloc))  # HTTP/2 carried authority as a pseudo-header
    if body:
        headers.append(("Content-Length", str(len(body))))

    http_headers = StatusAndHeaders(f"{method} {path} HTTP/1.1", headers)
    payload = BytesIO(body) if body else None
    return writer.create_warc_record(
        url, "request", http_headers=http_headers, payload=payload, length=len(body),
    )


_ROUTE_URLS_RE = re.compile(r"^route_urls(?:%5[Bb]|\[)\d+(?:%5[Dd]|\])=(.*)$")


def _bulk_route_singles(req_body: str, resp_bytes: bytes):
    """Split one captured multi-route ``bulk-route-definitions`` request/response into
    per-route SINGLE-route (body, response-bytes) pairs.

    At replay Instagram asks for routes one at a time; wabac's generic matcher then
    picks a stored record by overall similarity, so a lone single-route request gets
    mis-served the wrong multi-route batch. Emitting a single-route record per route
    (same shape the app requests at replay, carrying only that route's definition)
    lets stock wabac serve each correctly. Returns [] if the body isn't the expected
    Instagram route-definition envelope."""
    text = resp_bytes.decode("utf-8", "replace")
    prefix = "for (;;);" if text.startswith("for (;;);") else ""
    try:
        data = json.loads(text[len(prefix):])
    except Exception:
        return []
    payload = data.get("payload") if isinstance(data, dict) else None
    payloads = payload.get("payloads") if isinstance(payload, dict) else None
    if not isinstance(payloads, dict) or len(payloads) <= 1:
        return []  # nothing to split (not a multi-route batch)

    # non-route params from the captured request (routing_namespace, session tokens),
    # kept so each synthetic key resembles the app's real replay request.
    others = [p for p in (req_body or "").split("&")
              if p and not _ROUTE_URLS_RE.match(p)]

    out = []
    for route, value in payloads.items():
        body = "&".join(["route_urls[0]=" + quote(route, safe="")] + others)
        new_payload = {**payload, "payloads": {route: value}}
        single = prefix + json.dumps({**data, "payload": new_payload}, separators=(",", ":"))
        out.append((body, single.encode("utf-8")))
    return out


def _write_warc(har_path: Path, warc_path: Path, page_url: Optional[str]) -> Optional[str]:
    """Stream the HAR, merge 206 media per-URL, write a gzipped WARC.

    Returns the primary page URL to use (the passed ``page_url`` if given, else the
    first captured text/html 200 GET document -- guaranteed to be a stored record).
    """
    media: dict[str, dict] = {}
    primary_url = page_url
    n_records, n_media_entries, n_synth = 0, 0, 0

    with open(har_path, "rb") as fh, open(warc_path, "wb") as out:
        writer = WARCWriter(out, gzip=True)
        writer.write_record(writer.create_warcinfo_record(
            warc_path.name,
            {"software": "InstagramArchiver har_to_wacz", "format": "WARC File Format 1.0"},
        ))

        for entry in ijson.items(fh, "log.entries.item"):
            request = entry.get("request", {}) or {}
            response = entry.get("response", {}) or {}
            url = request.get("url")
            if not url or not url.startswith("http"):
                continue
            status = response.get("status") or 0
            if status <= 0:  # failed / no response captured
                continue

            method = (request.get("method") or "GET").upper()
            content = response.get("content", {}) or {}
            mime = (content.get("mimeType") or "").split(";")[0].strip().lower()
            body = _decode_body(content)
            ts_iso = _iso_to_warc_date(entry.get("startedDateTime"))

            if _is_mergeable_media(url, mime, status, entry):
                n_media_entries += 1
                key = _media_key(url)
                m = media.setdefault(
                    key, {"segments": [], "total": None, "headers": None,
                          "mime": "", "ts": None, "url": None}
                )
                start, _end, total = _segment_range(entry, url)
                # Some captures label a full-length body with a partial Content-Range
                # (the body actually starts at byte 0 but the header claims a tail);
                # trusting the header there prepends a gap and corrupts the file. When a
                # response body already spans the whole resource, it IS the complete file
                # -- place it at offset 0. (Guarded by a known Content-Range total, so it
                # never touches Instagram's range chunks, which are 200s with the range
                # in the URL and no total.)
                if total and len(body) >= total:
                    start = 0
                m["segments"].append((start or 0, body))
                if total:
                    m["total"] = max(m["total"] or 0, total)
                if m["url"] is None:  # store under the (query-preserving) whole-file URL
                    m["url"] = _whole_file_url(url)
                if m["headers"] is None:
                    m["headers"], m["mime"] = response.get("headers"), mime
                if ts_iso and (m["ts"] is None or ts_iso < m["ts"]):
                    m["ts"] = ts_iso
                continue

            # Non-media response record.
            if (primary_url is None and method == "GET"
                    and status == 200 and mime == "text/html"):
                primary_url = url
            resp_rec = _build_response_record(
                writer, url, status, response.get("statusText", ""),
                response.get("headers"), body, mime, ts_iso, drop_range=False)

            # For POST/PUT, also write a request record and pair them: js-wacz's
            # warcio.js indexer folds the request body into the CDX key (the same
            # __wb_method transform wabac recomputes at replay), so GraphQL/API POSTs
            # match. GET needs none (keyed by URL alone), so we skip the extra record.
            if method in ("POST", "PUT"):
                req_rec = _build_request_record(writer, request, url, method)
                writer.write_request_response_pair(req_rec, resp_rec)
                # bulk-route-definitions: also emit per-route single-route records so
                # stock wabac serves each route correctly at replay (see module docs).
                if method == "POST" and "bulk-route-definitions" in urlsplit(url).path:
                    req_body = (request.get("postData") or {}).get("text", "") or ""
                    for s_body, s_resp in _bulk_route_singles(req_body, body):
                        s_request = {
                            "method": "POST", "url": url,
                            "headers": [{"name": "Content-Type",
                                         "value": "application/x-www-form-urlencoded"}],
                            "postData": {"text": s_body},
                        }
                        s_resp_rec = _build_response_record(
                            writer, url, 200, "OK", response.get("headers"), s_resp,
                            mime, ts_iso, drop_range=False)
                        s_req_rec = _build_request_record(writer, s_request, url, "POST")
                        writer.write_request_response_pair(s_req_rec, s_resp_rec)
                        n_synth += 1
            else:
                writer.write_record(resp_rec)
            n_records += 1

        # Emit one merged 200 per media resource (response-only: a merged video
        # has no single originating request).
        for key, m in media.items():
            data, gaps = _assemble(m["segments"], m["total"])
            if gaps:
                covered = len(data) - sum(b - a for a, b in gaps)
                print(f"[har_to_wacz] WARNING: {key} incomplete "
                      f"({covered}/{len(data)} bytes; {len(gaps)} gap(s)) -- best-effort merge")
            resp_rec = _build_response_record(
                writer, m["url"] or key, 200, "OK", m["headers"], data,
                m["mime"] or "video/mp4", m["ts"], drop_range=True)
            writer.write_record(resp_rec)
            n_records += 1

    print(f"[har_to_wacz] Wrote {n_records} records "
          f"({len(media)} media resources merged from {n_media_entries} segments; "
          f"{n_synth} per-route bulk-route-definition records synthesized) "
          f"to {warc_path.name}")
    return primary_url


def _primary_from_metadata(har_path: Path) -> Optional[str]:
    """Fall back to the archive's recorded target_url when no HTML doc was found."""
    meta = har_path.parent / "metadata.json"
    if meta.exists():
        try:
            return json.loads(meta.read_text(encoding="utf-8")).get("target_url")
        except Exception:
            return None
    return None


def _js_wacz_dir() -> Path:
    """Directory of the vendored Node packager (utils/wacz_packager/)."""
    from root_anchor import ROOT_DIR
    return Path(ROOT_DIR) / "utils" / "wacz_packager"


def _ensure_js_wacz() -> Path:
    """Ensure js-wacz's node_modules are installed; return the path to its CLI.
    Mirrors the download-once pattern of ffmpeg_installer/par2_installer."""
    pkg_dir = _js_wacz_dir()
    cli = pkg_dir / "node_modules" / "@harvard-lil" / "js-wacz" / "bin" / "cli.js"
    if cli.exists():
        return cli

    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError(
            "Node.js/npm is required to package the WACZ (js-wacz). Install Node 18+ "
            "and ensure `npm` is on PATH."
        )
    print("[har_to_wacz] Installing js-wacz (one-time `npm install`)...")
    subprocess.run([npm, "install"], check=True, cwd=str(pkg_dir))
    if not cli.exists():
        raise RuntimeError(f"js-wacz install failed: {cli} not found after npm install")
    return cli


def _package_wacz(warc_path: Path, output_path: Path, primary_url: Optional[str]) -> None:
    """Package the WARC into a WACZ via js-wacz (warcio.js) -- the SAME toolchain
    replayweb.page uses at replay, so CDX keys (SURT + POST __wb_method/body) match.
    Passing --url makes js-wacz emit the seed page pointing at the primary URL."""
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js 18+ is required to package the WACZ (js-wacz).")
    cli = _ensure_js_wacz()

    # js-wacz expands -f through `glob`, which treats Windows backslashes as escapes.
    # Run from the WARC's directory and pass a bare filename so the pattern has no
    # path separators; give -o a forward-slash absolute path (Node accepts it on Win).
    cmd = [node, str(cli), "create", "-f", warc_path.name,
           "-o", output_path.as_posix()]
    if primary_url:
        cmd += ["--url", primary_url]
    subprocess.run(cmd, check=True, cwd=str(warc_path.parent))
    _fix_datapackage_hashes(output_path)


def _fix_datapackage_hashes(wacz_path: Path) -> None:
    """js-wacz 0.1.6 records a datapackage.json hash for ``archive/data.warc.gz`` that
    does not match the bytes it actually stored (same length, different digest), which
    fails ``wacz validate`` and breaks the archive's self-integrity. Recompute every
    resource hash over the real stored bytes and regenerate datapackage-digest.json so
    the WACZ is internally consistent -- essential for an evidentiary archive.

    Streams each member into a fresh zip, hashing its content in the same pass, so the
    multi-MB ``data.warc.gz`` is never buffered in memory."""
    import hashlib
    import zipfile

    dp_name, digest_name = "datapackage.json", "datapackage-digest.json"
    tmp = wacz_path.with_name(wacz_path.name + ".tmp")
    hashes: dict[str, tuple[int, str]] = {}  # member -> (bytes, "sha256:<hex>")

    with zipfile.ZipFile(wacz_path) as zin, zipfile.ZipFile(tmp, "w") as zout:
        # Copy every member except the two manifests verbatim, hashing the (decoded)
        # content in the same streaming pass. Fresh ZipInfos avoid carrying stale
        # CRC/flag bits from the source entry.
        for info in zin.infolist():
            if info.filename in (dp_name, digest_name):
                continue  # rewritten below, once all resource hashes are known
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            h, n = hashlib.sha256(), 0
            with zin.open(info) as src, zout.open(zi, "w") as dst:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    h.update(chunk)
                    n += len(chunk)
                    dst.write(chunk)
            hashes[info.filename] = (n, "sha256:" + h.hexdigest())

        # datapackage.json: point every resource at its real stored bytes/hash.
        dp = json.loads(zin.read(dp_name))
        for r in dp.get("resources", []):
            hb = hashes.get(r["path"])
            if hb is not None:
                r["bytes"], r["hash"] = hb
        dp_bytes = json.dumps(dp, indent=2).encode("utf-8")
        zout.writestr(dp_name, dp_bytes, zipfile.ZIP_DEFLATED)

        # datapackage-digest.json: hash over the regenerated datapackage.json.
        try:
            digest = json.loads(zin.read(digest_name))
        except KeyError:
            digest = {"path": dp_name}
        digest.pop("signedData", None)  # any prior signature no longer applies
        digest["hash"] = "sha256:" + hashlib.sha256(dp_bytes).hexdigest()
        zout.writestr(digest_name, json.dumps(digest, indent=2).encode("utf-8"),
                      zipfile.ZIP_DEFLATED)

    tmp.replace(wacz_path)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def generate_wacz(har_path: Path, output_path: Optional[Path] = None,
                  page_url: Optional[str] = None) -> Path:
    """Convert ``har_path`` into a replayable WACZ. Returns the output path."""
    har_path = Path(har_path)
    if not har_path.exists():
        raise FileNotFoundError(f"HAR file not found: {har_path}")
    output_path = Path(output_path) if output_path else har_path.with_suffix(".wacz")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory() as tmp:
        warc_path = Path(tmp) / "data.warc.gz"
        primary_url = _write_warc(har_path, warc_path, page_url)
        if not primary_url:
            primary_url = _primary_from_metadata(har_path)
        if primary_url:
            print(f"[har_to_wacz] Primary page: {primary_url}")
        else:
            print("[har_to_wacz] WARNING: no primary page URL found -- WACZ may not be navigable")
        _package_wacz(warc_path, output_path, primary_url)

    print(f"[har_to_wacz] WACZ written to: {output_path}")
    return output_path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert a HAR into a replayable WACZ (merges 206 byte-range video)."
    )
    parser.add_argument("har_path", nargs="?", help="Path to the input .har file")
    parser.add_argument("-o", "--output", help="Output .wacz path (default: alongside the HAR)")
    parser.add_argument("--url", dest="page_url",
                        help="Primary page URL (default: first captured text/html document)")
    args = parser.parse_args(argv)

    har = args.har_path or input("Enter the path to the HAR file: ").strip().strip('"').strip("'")
    generate_wacz(Path(har), Path(args.output) if args.output else None, args.page_url)


if __name__ == "__main__":
    main()
