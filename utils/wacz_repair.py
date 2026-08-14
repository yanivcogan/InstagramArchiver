"""Repair Meta/Instagram WACZ captures so that they replay in wabac.js
(replayweb.page) with the original site UI intact.

Why a repair step is needed
---------------------------
A WACZ of instagram.com contains everything the browser received, but the
Instagram web app is not a static page: it boots a module loader (Meta's
``Bootloader``) that resolves components against a *resource map* which the
live server delivers incrementally, in fragments, across many responses. It
also lazily fetches code, translations and route definitions *while* the page
hydrates. Replay changes two things that this design is sensitive to:

1. Nothing is live. Any request the capture did not record 404s. A single
   missing code chunk or translation file leaves a module permanently
   undefined, and React's Suspense boundary that waits for it never retries
   (its retry lane is empty), so the affected part of the UI stays a grey
   placeholder forever - usually with no console error at all.
2. Everything is instant. Responses come from a local archive, so hydration
   reaches lazily-loaded components far earlier, relative to their loads,
   than it did live.

The repairs below address those effects. They are deliberately constrained:

* **Generic** - every repair is driven by data found in the archive itself
  (the page's own resource maps, the module definitions inside the archived
  chunks). Nothing is keyed to a particular account, post, build number or
  file name.
* **Minimal** - each repair first checks whether the archive already works.
  Present, non-empty resources are never replaced; missing ones are filled
  from the archive itself before any external source is considered.
* **Justifiable** - no repair touches user-visible archived content. The
  things this tool adds or rewrites are: module/resource bookkeeping
  (which file defines which module), Meta's own UI string tables, script
  loading order, and code chunks recovered from the same or a donor capture.
  Post captions, usernames, counts, comments and media are copied verbatim
  and are never synthesised, substituted or re-attributed.

Every intervention is recorded and can be written out as a Markdown report
(``--report``) so that the modifications accompanying an evidentiary archive
can be disclosed precisely.

Usage
-----
    uv run utils/wacz_repair.py INPUT.wacz -o OUTPUT.wacz \
        [--donor OTHER.wacz ...] [--report report.md] \
        [--allow-network] [--no-cross-build] [--dry-run]

``--donor`` archives are other captures of the same site (e.g. the full
session export a partial export was cut from). They are used only as a source
of resources that are missing from the input.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from warcio.archiveiterator import ArchiveIterator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.har_to_wacz import generate_wacz  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Meta ships combined code bundles whose filename is the concatenation of the
# 11-character names of the modules inside it, and whose body is those members
# joined by this delimiter, in the same order.
MEMBER_NAME_LEN = 11
PKG_DELIM_RE = re.compile(rb";?/\*FB_PKG_DELIM\*/\n?")

DATA_SJS_RE = re.compile(
    rb'(<script[^>]*?data-content-len=")(\d+)("[^>]*data-sjs[^>]*>)(.*?)(</script>)', re.S)
REV_RE = re.compile(rb'"consistency":\{"rev":(\d+)\}')
DEFERRED_ROOT_RE = re.compile(rb'"__dr":"([^"]+)"')
MODULE_DEF_RE = re.compile(rb'__d\("([A-Za-z0-9_.\-$]+)"')
VIRTUAL_REF_RE = re.compile(rb'"([A-Za-z0-9_.\-]+\$fbt_virtual)"')
CR_REF_RE = re.compile(rb'"(cr:\d+)"')
CR_DEF_RE = re.compile(rb'\["(cr:\d+)",\[[^\[\]]*\],\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\},-1\]')
WB_METHOD_RE = re.compile(r"[?&]__wb_method=([A-Z]+)&?")
TRANSLATION_URL_RE = re.compile(
    rb"https:[\\/]{1,4}[a-z0-9.-]+[\\/]{1,2}rsrc-translations\.php(?:[\\/]{1,2}[A-Za-z0-9_.+-]+)+\.js")

ASSET_URL_RE = re.compile(
    rb"https:[\\/]{1,4}[a-z0-9.-]+[\\/]{1,2}rsrc(?:-translations)?\.php(?:[\\/]{1,2}[A-Za-z0-9_.,+-]+)+\.(?:js|css)")

TEXTY = ("html", "javascript", "ecmascript", "json", "text/")


# --------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------

@dataclass
class Record:
    """One archived HTTP exchange."""
    url: str
    method: str = "GET"
    status: int = 200
    headers: list = field(default_factory=list)
    mime: str = ""
    body: bytes = b""
    ts: str = ""
    post_body: Optional[bytes] = None
    req_headers: list = field(default_factory=list)
    provenance: str = "capture"

    @property
    def is_text(self) -> bool:
        return any(t in self.mime for t in TEXTY) or self.url.endswith((".js", ".json"))


def _clean_url(url: str) -> tuple[str, Optional[str], Optional[bytes]]:
    """ArchiveWeb.page full exports fold POSTs into the Target-URI as
    ``?__wb_method=POST&<body>``. Split that back apart."""
    m = WB_METHOD_RE.search(url)
    if not m:
        return url, None, None
    base = url[:m.start()]
    rest = url[m.end():]
    return base, m.group(1), rest.encode("utf-8", "replace")


def _maybe_gunzip(body: bytes) -> bytes:
    if body[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(body)
        except Exception:
            return body
    return body


def load_wacz(path: Path, *, provenance: str, code_only: bool = False) -> list[Record]:
    """Read every response record of a WACZ into memory.

    ``code_only`` keeps just the script/style/translation resources, which is
    all a donor archive is ever consulted for, and avoids holding a donor's
    media in memory."""
    out: list[Record] = []
    post_bodies: dict[str, tuple[str, bytes, list]] = {}
    with zipfile.ZipFile(path) as zf:
        warcs = [n for n in zf.namelist()
                 if n.startswith("archive/") and n.endswith((".warc.gz", ".warc"))]
        # first pass: request payloads, keyed by record id
        for wn in warcs:
            with zf.open(wn) as fh:
                for rec in ArchiveIterator(fh):
                    if rec.rec_type != "request":
                        continue
                    rid = rec.rec_headers.get_header("WARC-Concurrent-To") or ""
                    # warcio puts the request method in ``protocol`` for
                    # request records; only bodied methods carry a payload we
                    # may attach (a GET record's block is not a request body).
                    method = ((rec.http_headers.protocol if rec.http_headers else "")
                              or "GET").upper()
                    if method not in ("POST", "PUT", "PATCH"):
                        continue
                    try:
                        payload = rec.content_stream().read()
                    except Exception:
                        payload = b""
                    if rid:
                        req_headers = ([{"name": k, "value": v}
                                        for k, v in rec.http_headers.headers]
                                       if rec.http_headers else [])
                        post_bodies[rid.strip("<>")] = (method, payload, req_headers)
        for wn in warcs:
            with zf.open(wn) as fh:
                for rec in ArchiveIterator(fh):
                    if rec.rec_type not in ("response", "resource"):
                        continue
                    url = rec.rec_headers.get_header("WARC-Target-URI") or ""
                    if not url:
                        continue
                    if code_only and not ("rsrc.php" in url or "rsrc-translations" in url
                                          or url.endswith((".js", ".css"))
                                          or "/ajax/" in url or "graphql" in url):
                        continue
                    rid = (rec.rec_headers.get_header("WARC-Record-ID") or "").strip("<>")
                    try:
                        body = _maybe_gunzip(rec.content_stream().read())
                    except Exception:
                        continue
                    http = rec.http_headers
                    status, headers, mime = 200, [], ""
                    if http is not None:
                        parts = (http.statusline or "200 OK").split(" ")
                        try:
                            status = int(parts[0])
                        except ValueError:
                            status = 200
                        headers = [{"name": k, "value": v} for k, v in http.headers]
                        mime = http.get_header("Content-Type") or ""
                    url, folded_method, folded_body = _clean_url(url)
                    paired = post_bodies.get(rid)
                    method = folded_method or (paired[0] if paired else "GET")
                    post = folded_body if folded_body is not None else (
                        paired[1] if paired else None)
                    req_headers = paired[2] if paired else []
                    if folded_body is not None and not req_headers:
                        # a POST folded into the Target-URI carries a
                        # form-encoded body by construction
                        req_headers = [{"name": "Content-Type",
                                        "value": "application/x-www-form-urlencoded"}]
                    out.append(Record(url=url, method=method, status=status,
                                      headers=headers, mime=mime, body=body,
                                      ts=rec.rec_headers.get_header("WARC-Date") or "",
                                      post_body=post, req_headers=req_headers,
                                      provenance=provenance))
    return out


def primary_page_url(path: Path) -> Optional[str]:
    try:
        with zipfile.ZipFile(path) as zf:
            raw = zf.read("pages/pages.jsonl").decode("utf-8", "replace")
    except Exception:
        return None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("url"):
            return d["url"]
    return None


# --------------------------------------------------------------------------
# small parsing helpers
# --------------------------------------------------------------------------

def iter_json_objects(buf: bytes, key: str) -> Iterable[dict]:
    """Yield each JSON object that directly follows ``"<key>":`` in ``buf``."""
    kb = ('"%s":' % key).encode()
    i = 0
    while True:
        j = buf.find(kb, i)
        if j < 0:
            return
        k = j + len(kb)
        while k < len(buf) and buf[k:k + 1] in (b" ", b"\n", b"\t"):
            k += 1
        if k >= len(buf) or buf[k:k + 1] != b"{":
            i = j + len(kb)
            continue
        depth, in_str, esc, end = 0, False, False, None
        for m in range(k, len(buf)):
            c = buf[m:m + 1]
            if in_str:
                if esc:
                    esc = False
                elif c == b"\\":
                    esc = True
                elif c == b'"':
                    in_str = False
            elif c == b'"':
                in_str = True
            elif c == b"{":
                depth += 1
            elif c == b"}":
                depth -= 1
                if depth == 0:
                    end = m
                    break
        if end is None:
            return
        try:
            yield json.loads(buf[k:end + 1])
        except Exception:
            pass
        i = end + 1


def bundle_members(url: str) -> list[str]:
    """Member names encoded in a combined bundle URL (last one may be cut)."""
    stem = urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]
    if stem.endswith(".js"):
        stem = stem[:-3]
    if len(stem) <= MEMBER_NAME_LEN:
        return [stem]
    return [stem[i:i + MEMBER_NAME_LEN] for i in range(0, len(stem), MEMBER_NAME_LEN)]


def index_table(rsrc_map: dict) -> dict[int, str]:
    """Bootloader's resource-index table: csr sets reference resources by the
    integer indexes declared in each entry's ``p`` field."""
    table: dict[int, str] = {}
    for h, v in rsrc_map.items():
        if not isinstance(v, dict):
            continue
        for tok in (v.get("p") or "").lstrip(":").split(","):
            tok = tok.strip()
            if tok.isdigit():
                table.setdefault(int(tok), h)
    return table


def expand_resources(hashes: Iterable[str], rsrc_map: dict,
                     table: dict[int, str]) -> tuple[list[dict], list[int]]:
    """Resolve a component's resource hashes (expanding csr index sets).
    Returns (entries, unresolved_indexes)."""
    entries, unresolved = [], []
    for h in hashes:
        v = rsrc_map.get(h)
        if not isinstance(v, dict):
            continue
        if v.get("type") == "csr":
            for tok in (v.get("src") or "").lstrip(":").split(","):
                tok = tok.strip()
                if not tok.isdigit():
                    continue
                idx = int(tok)
                hh = table.get(idx)
                if hh is None:
                    unresolved.append(idx)
                elif isinstance(rsrc_map.get(hh), dict):
                    entries.append(rsrc_map[hh])
        else:
            entries.append(v)
    return entries, unresolved


# --------------------------------------------------------------------------
# repairer
# --------------------------------------------------------------------------

class WaczRepairer:
    def __init__(self, records: list[Record], donors: list[Record], *,
                 allow_network: bool = False, allow_cross_build: bool = True):
        self.records = records
        self.donors = donors
        self.allow_network = allow_network
        self.allow_cross_build = allow_cross_build
        self.report: list[dict] = []
        self.added: list[Record] = []

        self.by_url: dict[str, Record] = {}
        for r in records:
            self._offer(self.by_url, r)
        self.donor_by_url: dict[str, Record] = {}
        for r in donors:
            self._offer(self.donor_by_url, r)

        # analysis products
        self.merged: dict[str, dict] = {}
        self.docs: list[Record] = []
        self.module_chunk: dict[str, str] = {}
        self.virtual_sources: dict[str, list[str]] = {}
        self.cr_defines: dict[str, dict] = {}
        self.cr_referenced: dict[str, set] = {}
        self.chunk_revs: dict[str, set] = {}
        self._members: Optional[dict] = None

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _offer(index: dict[str, Record], r: Record) -> None:
        """Keep the most useful record per URL (200 first, then largest)."""
        cur = index.get(r.url)
        if cur is None:
            index[r.url] = r
            return
        better = (r.status == 200, len(r.body)) > (cur.status == 200, len(cur.body))
        if better:
            index[r.url] = r

    def note(self, kind: str, target: str, source: str, reason: str) -> None:
        self.report.append({"kind": kind, "target": target,
                            "source": source, "reason": reason})

    def serves(self, url: Optional[str], *, min_len: int = 1) -> bool:
        r = self.by_url.get(url or "")
        return bool(r and r.status == 200 and len(r.body) >= min_len)

    def any_body(self, url: str) -> Optional[Record]:
        """The best available body for a URL, from the input or a donor."""
        r = self.by_url.get(url)
        if r and r.status == 200 and r.body:
            return r
        d = self.donor_by_url.get(url)
        if d and d.status == 200 and d.body:
            return d
        return None

    def document_revs(self) -> set:
        """Build revisions of the pages this archive actually contains."""
        revs = set()
        for doc in self.docs:
            m = REV_RE.search(doc.body)
            if m:
                revs.add(m.group(1).decode())
        return revs

    def add_record(self, url: str, body: bytes, mime: str, *,
                   provenance: str, ts: str = "", method: str = "GET",
                   post_body: Optional[bytes] = None) -> Record:
        rec = Record(url=url, method=method, status=200,
                     headers=[{"name": "content-type", "value": mime}],
                     mime=mime, body=body, ts=ts, post_body=post_body,
                     req_headers=([{"name": "Content-Type",
                                    "value": "application/x-www-form-urlencoded"}]
                                  if post_body is not None else []),
                     provenance=provenance)
        self.added.append(rec)
        self._offer(self.by_url, rec)
        return rec

    # -- analysis --------------------------------------------------------
    def analyze(self) -> None:
        """Index the archive: resource-map fragments, module definitions,
        translation tables and conditional-module aliases.

        Donor captures are indexed alongside the input: they are only a
        *lookup* of where a given module or interface-string table lives, and
        anything actually served from them is recorded as such."""
        for r in self.records + self.donors:
            if not r.is_text or not r.body:
                continue
            from_input = r.provenance == "capture"
            body = r.body
            is_html = "html" in r.mime or body[:200].lstrip()[:15].lower().startswith(b"<!doctype html")
            if is_html:
                m_rev = REV_RE.search(body)
                if m_rev:
                    if from_input:
                        self.docs.append(r)
                    # a page carries part of its build's resource map inline
                    page_rsrc, page_comp = self._page_maps(body)
                    if page_rsrc or page_comp:
                        self._merge_fragment({"consistency": {"rev": int(m_rev.group(1))},
                                              "rsrcMap": page_rsrc, "compMap": page_comp})
            # resource-map fragments (delivered incrementally, in many shapes)
            if b'"rsrcMap"' in body or b'"compMap"' in body:
                self._collect_maps(body)
            # module definitions inside archived code chunks
            if b"__d(" in body and ("javascript" in r.mime or r.url.endswith(".js")):
                for name in MODULE_DEF_RE.findall(body):
                    self.module_chunk.setdefault(name.decode(), r.url)
            # translation tables define the $fbt_virtual modules
            if "rsrc-translations" in r.url and body[:1] == b"{":
                try:
                    data = json.loads(body)
                except Exception:
                    data = None
                if isinstance(data, dict):
                    for v in data.get("virtual_modules") or []:
                        self.virtual_sources.setdefault(v, []).append(r.url)
            # conditional-module aliases
            if b'["cr:' in body:
                rev = self._rev_of(r, body)
                if rev:
                    tgt = self.cr_defines.setdefault(rev, {})
                    for raw in CR_DEF_RE.findall(body):
                        try:
                            entry = json.loads(raw)
                        except Exception:
                            continue
                        tgt.setdefault(entry[0], entry)
        # cr references are attributed per build once the maps are known
        for rev, m in self.merged.items():
            for v in m.get("rsrcMap", {}).values():
                if isinstance(v, dict) and v.get("src"):
                    self.chunk_revs.setdefault(v["src"], set()).add(rev)
        for r in self.records + self.donors:
            if not (r.url.endswith(".js") or "javascript" in r.mime):
                continue
            revs = self.chunk_revs.get(r.url)
            if not revs or b'"cr:' not in r.body:
                continue
            refs = {m.decode() for m in CR_REF_RE.findall(r.body)}
            for rev in revs:
                self.cr_referenced.setdefault(rev, set()).update(refs)

    def _rev_of(self, r: Record, body: bytes) -> Optional[str]:
        m = re.search(r"__spin_r=(\d+)", r.url)
        if m:
            return m.group(1)
        m2 = REV_RE.search(body)
        return m2.group(1).decode() if m2 else None

    def _collect_maps(self, body: bytes) -> None:
        for frag in iter_json_objects(body, "hblp"):
            self._merge_fragment(frag)
        # some payloads carry rsrcMap/compMap without the hblp wrapper
        if b'"hblp"' not in body:
            rev = None
            m = REV_RE.search(body)
            if m:
                rev = m.group(1).decode()
            if rev:
                frag = {"consistency": {"rev": int(rev)}}
                for key in ("rsrcMap", "compMap"):
                    merged: dict = {}
                    for obj in iter_json_objects(body, key):
                        merged.update(obj)
                    if merged:
                        frag[key] = merged
                if len(frag) > 1:
                    self._merge_fragment(frag)

    def _merge_fragment(self, frag: dict) -> None:
        rev = str((frag.get("consistency") or {}).get("rev") or "")
        if not rev:
            return
        tgt = self.merged.setdefault(rev, {"consistency": {"rev": int(rev)},
                                           "rsrcMap": {}, "compMap": {}})
        for key in ("rsrcMap", "compMap"):
            src = frag.get(key) or {}
            if isinstance(src, dict):
                for k, v in src.items():
                    tgt[key].setdefault(k, v)

    # -- resource recovery ----------------------------------------------
    def recover(self, url: str, want_rev: Optional[str] = None) -> Optional[tuple[bytes, str]]:
        """Find a body for ``url`` without inventing content.

        Order of preference, most faithful first:
          1. a donor capture holding the very same URL;
          2. the member carved out of a combined bundle that contains it
             (bundle URLs list their members, bodies are delimiter-joined);
          3. the same logical resource from another build (resource hashes
             are stable across builds, only the file name changes);
          4. the live CDN / Wayback Machine, if --allow-network.
        """
        d = self.donor_by_url.get(url)
        if d and d.status == 200 and d.body:
            return d.body, f"donor archive record {url}"

        member = bundle_members(url)[0] if len(bundle_members(url)) == 1 else None
        if member:
            hit = self._from_combined_bundle(member, want_rev)
            if hit:
                return hit

        if self.allow_cross_build:
            hit = self._cross_build(url)
            if hit:
                return hit

        if self.allow_network:
            hit = self._from_network(url)
            if hit:
                return hit
        return None

    def _member_index(self) -> dict:
        if self._members is None:
            idx: dict = {}
            for index in (self.by_url, self.donor_by_url):
                for u, r in index.items():
                    if "rsrc.php" not in u or not r.body or r.status != 200:
                        continue
                    members = bundle_members(u)
                    if len(members) < 2:
                        continue
                    for m in members:
                        idx.setdefault(m, []).append(u)
            self._members = idx
        return self._members

    def _from_combined_bundle(self, member: str,
                              want_rev: Optional[str] = None) -> Optional[tuple[bytes, str]]:
        candidates = self._member_index().get(member, [])
        for u in candidates:
            for index in (self.by_url, self.donor_by_url):
                r = index.get(u)
                if r is None or not r.body or r.status != 200:
                    continue
                if want_rev is not None:
                    # only carve a member out of a bundle belonging to the
                    # same build; mixing builds silently would put code from
                    # another release into this page
                    revs = self.chunk_revs.get(u)
                    if not revs or want_rev not in revs:
                        continue
                members = bundle_members(u)
                parts = PKG_DELIM_RE.split(r.body)
                if parts and not parts[0].strip():
                    parts = parts[1:]
                if len(parts) != len(members):
                    continue
                seg = parts[members.index(member)]
                if seg.strip():
                    return seg, (f"member '{member}' extracted from combined bundle {u} "
                                 f"({r.provenance})")
        return None

    def _cross_build(self, url: str) -> Optional[tuple[bytes, str]]:
        logical, home_rev = None, None
        for rev, m in self.merged.items():
            for h, v in m.get("rsrcMap", {}).items():
                if isinstance(v, dict) and v.get("src") == url:
                    logical, home_rev = h, rev
                    break
            if logical:
                break
        if not logical:
            return None
        for rev, m in self.merged.items():
            if rev == home_rev:
                continue
            v = m.get("rsrcMap", {}).get(logical)
            if not isinstance(v, dict) or not v.get("src"):
                continue
            alt = v["src"]
            for index in (self.by_url, self.donor_by_url):
                r = index.get(alt)
                if r and r.status == 200 and r.body:
                    return r.body, (f"same logical resource '{logical}' from build {rev} "
                                    f"({alt}, {r.provenance})")
            member = bundle_members(alt)
            if len(member) == 1:
                hit = self._from_combined_bundle(member[0])
                if hit:
                    return hit[0], (f"same logical resource '{logical}' from build {rev}: "
                                    + hit[1])
        return None

    def _from_network(self, url: str) -> Optional[tuple[bytes, str]]:
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = resp.read()
            if body:
                return body, f"live fetch of {url}"
        except Exception:
            pass
        try:
            q = urllib.parse.quote(url, safe="")
            with urllib.request.urlopen(
                    f"http://archive.org/wayback/available?url={q}", timeout=12) as resp:
                snap = json.loads(resp.read()).get("archived_snapshots", {}).get("closest")
            if snap and snap.get("available"):
                with urllib.request.urlopen(
                        f"https://web.archive.org/web/{snap['timestamp']}id_/{url}",
                        timeout=25) as resp:
                    body = resp.read()
                if body:
                    return body, f"Wayback Machine snapshot {snap['timestamp']} of {url}"
        except Exception:
            pass
        return None

    # -- repairs ---------------------------------------------------------
    def repair_data_sjs_lengths(self) -> None:
        """The capture tool rewrites URLs inside the inline ``data-sjs``
        payloads but leaves their ``data-content-len`` attribute untouched.
        Meta's payload listener compares the two and, on a mismatch, retries
        the payload 5000 times at 20ms - a ~100s stall per payload before the
        app starts. Only the declared byte count is corrected; the payload
        itself is not modified."""
        for doc in self.docs:
            fixed = [0]

            def repl(m):
                declared, content = int(m.group(2)), m.group(4)
                if declared == len(content):
                    return m.group(0)
                fixed[0] += 1
                return m.group(1) + str(len(content)).encode() + m.group(3) + content + m.group(5)

            new = DATA_SJS_RE.sub(repl, doc.body)
            if fixed[0]:
                doc.body = new
                self.note("data-sjs length", doc.url, "recomputed from payload bytes",
                          f"{fixed[0]} inline payload(s) declared a byte count that no "
                          f"longer matched their (capture-rewritten) content")

    def repair_missing_resources(self) -> None:
        """Fill code/style resources that the page's own resource map points
        at but that the capture does not contain (typical of partial exports,
        or of assets the browser served from cache)."""
        wanted: list[tuple[str, str]] = []
        # assets named anywhere in the archived pages or their code - script
        # and preload tags, and the loader's own lazy requests. A capture
        # misses these whenever the browser served them from its own cache,
        # and a single missing one can strand a whole screen (a highlight
        # viewer, say) on a spinner.
        page_revs = sorted(self.document_revs())
        named: set = set()
        for r in self.records:
            if not r.is_text or b"rsrc" not in r.body:
                continue
            for raw in ASSET_URL_RE.findall(r.body):
                url = raw.decode("utf-8", "replace").replace("\\/", "/")
                if "rsrc-translations" not in url and not self.serves(url):
                    named.add(url)
        for url in sorted(named):
            # prefer the build the resource is known to belong to; otherwise
            # try each build this archive contains a page for
            for rev in sorted(self.chunk_revs.get(url) or ()) or page_revs:
                wanted.append((url, rev))
        for rev in page_revs:
            for v in self.merged.get(rev, {}).get("rsrcMap", {}).values():
                if not isinstance(v, dict) or v.get("type") not in ("js", "css"):
                    continue
                src = v.get("src")
                if src and not self.serves(src):
                    wanted.append((src, rev))
        for url, rev in sorted(set(wanted)):
            if self.serves(url):  # already supplied (e.g. via another build's entry)
                continue
            hit = self.recover(url, rev)
            if not hit:
                continue
            body, source = hit
            mime = "text/css" if url.endswith(".css") else "application/x-javascript"
            self.add_record(url, body, mime, provenance=source)
            self.note("missing resource", url, source,
                      "referenced by the capture's own resource map but absent from the "
                      "archive; without it the modules it defines stay undefined")

    def repair_translations(self) -> None:
        """Meta keeps each code chunk's UI strings in a separate
        ``rsrc-translations.php`` file, whose ``virtual_modules`` list is what
        actually defines the ``X$fbt_virtual`` modules that components depend
        on. When such a file is missing from the capture, every component in
        that chunk waits forever on an undefined dependency and its part of
        the page stays a placeholder.

        The gap is filled with a translation table **already present in the
        archive** that defines the missing virtual modules. Only Meta's own
        interface strings are involved; no archived post content is affected,
        and files that are present are never replaced."""
        for rev in self.document_revs():
            for v in self.merged.get(rev, {}).get("rsrcMap", {}).values():
                if not isinstance(v, dict) or v.get("type") != "js":
                    continue
                src, tsrc = v.get("src"), v.get("tsrc")
                if not tsrc or not self.serves(src) or self.serves(tsrc, min_len=60):
                    continue
                chunk = self.by_url[src].body
                # Bootloader expects one "<Module>$fbt_virtual" per module in
                # the chunk that carries translatable strings; those are what
                # the chunk's translation table defines.
                needed = {n.decode() + "$fbt_virtual"
                          for n in MODULE_DEF_RE.findall(chunk)}
                needed &= set(self.virtual_sources)
                if not needed:
                    continue
                same_rev = {e.get("tsrc") for e in
                            self.merged.get(rev, {}).get("rsrcMap", {}).values()
                            if isinstance(e, dict) and e.get("tsrc")}
                best, best_key = None, (0, 0, 0)
                for cand_url in {u for n in needed for u in self.virtual_sources.get(n, [])}:
                    rec = self.any_body(cand_url)
                    if not rec or len(rec.body) < 60:
                        continue
                    try:
                        data = json.loads(rec.body)
                    except Exception:
                        continue
                    hits = len(needed & set(data.get("virtual_modules") or []))
                    if not hits:
                        continue
                    key = (hits, 1 if cand_url in same_rev else 0, -len(rec.body))
                    if key > best_key:
                        best, best_key = rec, key
                if not best:
                    continue
                best_hit = best_key[0]
                self.add_record(tsrc, best.body, "application/x-javascript",
                                provenance=f"archived translation table {best.url}")
                self.note("missing translations", tsrc,
                          f"archived translation table {best.url}",
                          f"interface-string table for {Path(urllib.parse.urlsplit(src).path).name} "
                          f"is absent; supplied a table from the same capture defining "
                          f"{best_hit}/{len(needed)} of the required virtual modules")

    def repair_referenced_translations(self) -> None:
        """Interface-string tables the archived pages name directly.

        A page names its chunks' companion string tables in its own markup,
        outside the resource map. Where such a table is absent from the
        capture - or was stored as an empty placeholder - the virtual modules
        it defines never come into existence and every component in the
        matching chunk waits for them forever. Each gap is filled with a table
        already present in the archive that defines those same virtual
        modules; tables that are present and non-empty are left untouched."""
        chunk_by_stem: dict[str, str] = {}
        for url in self.by_url:
            if "rsrc.php" not in url or not url.endswith(".js"):
                continue
            stem = urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1][:-3]
            if len(stem) == MEMBER_NAME_LEN:
                chunk_by_stem.setdefault(stem, url)

        referenced: set = set()
        for r in self.records:
            if not r.is_text or b"rsrc-translations" not in r.body:
                continue
            for raw in TRANSLATION_URL_RE.findall(r.body):
                referenced.add(raw.decode("utf-8", "replace").replace("\\/", "/"))

        for url in sorted(referenced):
            if self.serves(url, min_len=60):
                continue
            stem = urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1][:-3]
            members = [stem] if len(stem) == MEMBER_NAME_LEN else bundle_members(url)
            needed: set = set()
            for member in members:
                chunk = chunk_by_stem.get(member)
                if not chunk:
                    continue
                body = self.by_url[chunk].body
                needed |= {n.decode() + "$fbt_virtual"
                           for n in MODULE_DEF_RE.findall(body)}
            needed &= set(self.virtual_sources)
            if not needed:
                continue
            best, best_key = None, (0, 0)
            for cand in {u for n in needed for u in self.virtual_sources.get(n, [])}:
                other = self.any_body(cand)
                if not other or len(other.body) < 60:
                    continue
                try:
                    data = json.loads(other.body)
                except Exception:
                    continue
                hits = len(needed & set(data.get("virtual_modules") or []))
                key = (hits, -len(other.body))
                if hits and key > best_key:
                    best, best_key = other, key
            if not best:
                continue
            self.add_record(url, best.body, "application/x-javascript",
                            provenance=f"archived interface-string table {best.url}")
            self.note("interface strings", url,
                      f"archived table {best.url}",
                      f"table named by the page but "
                      f"{'stored empty' if self.by_url.get(url) else 'absent'}; supplied one "
                      f"from the archive defining {best_key[0]}/{len(needed)} of the virtual "
                      f"modules its chunk needs")

    def repair_post_aliases(self) -> None:
        """A replay client cannot reproduce POST bodies that contained
        session-derived tokens, so its request never matches the archived one
        and the call 404s. Where a URL has exactly one archived POST exchange,
        the mapping is unambiguous, so an additional alias record keyed to an
        empty body is emitted. No response content is altered."""
        by_path: dict[str, list[Record]] = {}
        for r in self.records:
            if r.method == "POST" and r.status == 200:
                p = urllib.parse.urlsplit(r.url)
                by_path.setdefault(f"{p.scheme}://{p.netloc}{p.path}", []).append(r)
        for path, group in by_path.items():
            # Endpoints called more than once (GraphQL and friends) return a
            # different answer per request body; an empty-body alias there
            # could hand the page another call's response, so they are left
            # alone. Only endpoints with a single archived exchange qualify.
            if len(group) != 1:
                continue
            r = group[0]
            url = r.url
            if not r.post_body:
                continue
            self.add_record(url, r.body, r.mime or "application/json",
                            provenance=f"alias of the single archived POST to {url}",
                            ts=r.ts, method="POST", post_body=b"")
            self.note("POST alias", url, "the archive's only POST exchange for this URL",
                      "replay cannot rebuild the original request body (session tokens); "
                      "an empty-body alias returns the same archived response")

    def repair_route_definitions(self) -> None:
        """In-page navigation asks ``/ajax/route-definition/`` for one route.
        Live, the app had already prefetched routes in bulk through
        ``/ajax/bulk-route-definitions/``, so the singular endpoint is often
        absent from a capture and every in-page navigation dies. Each singular
        response is assembled from the bulk response captured in this same
        session - the route payload is copied verbatim, only re-wrapped in the
        envelope the singular endpoint uses."""
        made = 0
        for r in list(self.records):
            if "/ajax/bulk-route-definitions/" not in r.url or not r.body:
                continue
            text = r.body.decode("utf-8", "replace")
            prefix = "for (;;);" if text.startswith("for (;;);") else ""
            try:
                data = json.loads(text[len(prefix):])
            except Exception:
                continue
            payloads = ((data.get("payload") or {}).get("payloads") or {})
            hsrp = data.get("hsrp") or {}
            rev = ((hsrp.get("hblp") or {}).get("consistency") or {}).get("rev") or ""
            for route, value in payloads.items():
                body = json.dumps({"__type": "first_response", "payload": value,
                                   "sr_payload": hsrp, "preloaders": []},
                                  separators=(",", ":"))
                req = ("client_previous_actor_id=&route_url="
                       + urllib.parse.quote(route, safe="")
                       + "&routing_namespace=igx_www"
                       + (f"&__rev={rev}" if rev else ""))
                self.add_record("https://www.instagram.com/ajax/route-definition/",
                                ("for (;;);" + body).encode(),
                                "application/x-javascript; charset=utf-8",
                                provenance=f"route '{route}' as captured in {r.url}",
                                ts=r.ts, method="POST", post_body=req.encode())
                made += 1
        if made:
            self.note("route definitions", "/ajax/route-definition/",
                      "the session's own bulk-route-definitions responses",
                      f"{made} single-route responses re-wrapped from captured bulk data "
                      f"so that in-page navigation resolves")

    # -- page payload injection -----------------------------------------
    def repair_documents(self, skip: Iterable[str] = ()) -> None:
        """Rewrite each archived page so the loader can do its job offline."""
        skip = set(skip)
        for doc in self.docs:
            m = REV_RE.search(doc.body)
            if not m:
                continue
            rev = m.group(1).decode()
            merged = self.merged.get(rev)
            if not merged:
                continue
            page_rsrc, page_comp = self._page_maps(doc.body)
            add_rsrc = {k: v for k, v in merged["rsrcMap"].items() if k not in page_rsrc}
            add_comp = {k: v for k, v in merged["compMap"].items() if k not in page_comp}

            rsrc_all = dict(page_rsrc)
            rsrc_all.update(merged["rsrcMap"])
            comp_all = dict(page_comp)
            comp_all.update(merged["compMap"])
            table = index_table(rsrc_all)

            preload, registered = ([], 0) if "preload" in skip else self._deferred_components(
                doc.body, rsrc_all, comp_all, table, add_rsrc, add_comp)

            defines = [] if "defines" in skip else self._needed_cr_defines(
                rev, doc.body, preload, comp_all, rsrc_all, table)
            if "maps" in skip:
                add_rsrc, add_comp = {}, {}

            head_payload: dict = {}
            if add_rsrc or add_comp:
                head_payload["require"] = [[
                    "Bootloader", "handlePayload", None,
                    [{"consistency": {"rev": int(rev)},
                      "rsrcMap": add_rsrc, "compMap": add_comp}]]]
            if defines:
                head_payload["define"] = defines
            body = doc.body
            if head_payload:
                body = self._insert_payload(body, head_payload, at_top=True)
                if add_rsrc or add_comp:
                    self.note("resource map", doc.url,
                              "resource-map fragments captured in this session",
                              f"consolidated {len(add_rsrc)} resource and {len(add_comp)} "
                              f"component entries the page itself does not carry; live these "
                              f"arrived in later responses that replay cannot reproduce")
                if defines:
                    self.note("conditional modules", doc.url,
                              "conditional-alias definitions captured in this session",
                              f"{len(defines)} 'cr:' alias(es) are referenced by archived code "
                              f"but defined only in on-demand responses that are no longer fetched")
            if preload:
                body = self._insert_payload(
                    body, {"require": [["Bootloader", "loadModules", None, [preload]]]},
                    at_top=False)
                self.note("deferred components", doc.url,
                          "the page's own deferred-dependency list",
                          f"loads {len(preload)} component(s) the page declares as deferred "
                          f"dependencies before hydration instead of during it"
                          + (f"; {registered} of them had to be re-associated with the archived "
                             f"chunk that defines them because the capture's resource-index "
                             f"table is incomplete" if registered else ""))
            doc.body = body

    def _page_maps(self, html: bytes) -> tuple[dict, dict]:
        rsrc: dict = {}
        comp: dict = {}
        for obj in iter_json_objects(html, "rsrcMap"):
            rsrc.update(obj)
        for obj in iter_json_objects(html, "compMap"):
            comp.update(obj)
        return rsrc, comp

    def _deferred_components(self, html: bytes, rsrc_all: dict, comp_all: dict,
                             table: dict, add_rsrc: dict, add_comp: dict) -> tuple[list, int]:
        """Components a route root declares as deferred dependencies.

        Live these load lazily while the page hydrates over the network; under
        replay hydration reaches them first and React never retries the
        boundary, so they must be ready up front. Where the capture's
        index table cannot resolve a component's resources, the component is
        re-associated with the archived chunk that actually defines it - a
        bookkeeping change only: the code served is the archived code."""
        preload: list[str] = []
        registered = 0
        for raw_root in DEFERRED_ROOT_RE.findall(html):
            root = raw_root.decode()
            entry = comp_all.get(root)
            if not isinstance(entry, dict):
                continue
            rdfds = entry.get("rdfds") or {}
            for mod in rdfds.get("m") or []:
                if mod in preload:
                    continue
                if self._component_loadable(mod, comp_all, rsrc_all, table):
                    self._pair_string_tables(mod, comp_all, rsrc_all, table, add_rsrc)
                    preload.append(mod)
                    continue
                chunk = self.module_chunk.get(mod)
                if not chunk or not self.serves(chunk):
                    continue
                h = self._hash_for(chunk, rsrc_all)
                if h is None:
                    h = "wr%08x" % (abs(hash(chunk)) % (1 << 31))
                    entry = {"type": "js", "src": chunk, "c": 1}
                    add_rsrc[h] = entry
                    rsrc_all[h] = entry
                self._ensure_string_table(h, rsrc_all, add_rsrc, mod)
                add_comp[mod] = {"r": [h]}
                comp_all[mod] = add_comp[mod]
                preload.append(mod)
                registered += 1
        return preload, registered

    def _translation_for_chunk(self, chunk_url: str) -> Optional[tuple[str, int, int]]:
        """The archived interface-string table that defines the
        ``$fbt_virtual`` modules of the code chunk at ``chunk_url``.

        Meta keeps a chunk's translatable strings in a companion file and
        derives one virtual module per translatable module from it. A chunk
        loaded without its companion leaves those virtual modules undefined,
        which is what freezes a component permanently. Returns
        (url, covered, needed)."""
        rec = self.by_url.get(chunk_url)
        if not rec:
            return None
        needed = {n.decode() + "$fbt_virtual" for n in MODULE_DEF_RE.findall(rec.body)}
        needed &= set(self.virtual_sources)
        if not needed:
            return None
        best, best_key = None, (0, 0)
        for cand in {u for n in needed for u in self.virtual_sources.get(n, [])}:
            other = self.any_body(cand)
            if not other or len(other.body) < 60:
                continue
            try:
                data = json.loads(other.body)
            except Exception:
                continue
            hits = len(needed & set(data.get("virtual_modules") or []))
            key = (hits, -len(other.body))
            if hits and key > best_key:
                best, best_key = other, key
        if not best:
            return None
        if not self.serves(best.url, min_len=60):
            self.add_record(best.url, best.body, "application/x-javascript",
                            provenance=f"archived interface-string table {best.url} "
                                       f"({best.provenance})")
        return best.url, best_key[0], len(needed)

    def _resource_pairs(self, hashes, rsrc_all: dict, table: dict) -> list:
        """(hash, entry) for a component's resources, expanding index sets."""
        out = []
        for h in hashes:
            v = rsrc_all.get(h)
            if not isinstance(v, dict):
                continue
            if v.get("type") == "csr":
                for tok in (v.get("src") or "").lstrip(":").split(","):
                    tok = tok.strip()
                    if not tok.isdigit():
                        continue
                    hh = table.get(int(tok))
                    if hh and isinstance(rsrc_all.get(hh), dict):
                        out.append((hh, rsrc_all[hh]))
            else:
                out.append((h, v))
        return out

    def _ensure_string_table(self, h: str, rsrc_all: dict, add_rsrc: dict,
                             mod: str) -> None:
        """Attach an archived interface-string table to one code resource, if
        it does not already have one the archive can serve."""
        res = rsrc_all.get(h)
        if not isinstance(res, dict) or res.get("type") != "js":
            return
        if not self.serves(res.get("src")):
            return
        if res.get("tsrc") and self.serves(res["tsrc"], min_len=60):
            return
        tr = self._translation_for_chunk(res["src"])
        if not tr:
            return
        paired = dict(res)
        paired["tsrc"] = tr[0]
        add_rsrc[h] = paired
        rsrc_all[h] = paired
        self.note("interface strings", mod, f"archived table {tr[0]}",
                  f"{Path(urllib.parse.urlsplit(res['src']).path).name} is paired with the "
                  f"string table defining {tr[1]}/{tr[2]} of its virtual modules; without "
                  f"it the component never finishes loading")

    def _pair_string_tables(self, mod: str, comp_all: dict, rsrc_all: dict,
                            table: dict, add_rsrc: dict) -> None:
        """Make sure every code resource of a component the page needs up
        front is paired with an interface-string table the archive can serve.

        A chunk whose companion table is missing (or is not named by the
        capture at all) leaves its ``$fbt_virtual`` modules undefined, and the
        component then waits for them forever."""
        entry = comp_all.get(mod)
        if not isinstance(entry, dict):
            return
        for h, _res in self._resource_pairs(entry.get("r") or [], rsrc_all, table):
            self._ensure_string_table(h, rsrc_all, add_rsrc, mod)

    def _component_loadable(self, mod: str, comp_all: dict, rsrc_all: dict,
                            table: dict) -> bool:
        entry = comp_all.get(mod)
        if not isinstance(entry, dict):
            return False
        entries, unresolved = expand_resources(entry.get("r") or [], rsrc_all, table)
        if unresolved:
            return False
        return any(self.serves(e.get("src")) for e in entries if isinstance(e, dict))

    @staticmethod
    def _hash_for(url: str, rsrc_all: dict) -> Optional[str]:
        for h, v in rsrc_all.items():
            if isinstance(v, dict) and v.get("src") == url:
                return h
        return None

    def _needed_cr_defines(self, rev: str, html: bytes, preload: list,
                           comp_all: dict, rsrc_all: dict, table: dict) -> list:
        """Conditional module aliases ("cr:N") select between implementations
        at load time. They are declared in the on-demand responses that the
        loader no longer needs to fetch once a component is preloaded, so the
        alias would be left dangling.

        Only aliases referenced by the code of the components this page
        preloads are supplied, and only when the page does not already declare
        them: a wider injection would define aliases for code paths the page
        never took."""
        have = {d.decode() for d in CR_DEF_RE.findall(html)}
        pool = self.cr_defines.get(rev, {})
        if not pool or not preload:
            return []
        referenced: set = set()
        for mod in preload:
            entry = comp_all.get(mod)
            if not isinstance(entry, dict):
                continue
            entries, _ = expand_resources(entry.get("r") or [], rsrc_all, table)
            for e in entries:
                rec = self.by_url.get((e or {}).get("src") or "")
                if rec and b'"cr:' in rec.body:
                    referenced.update(m.decode() for m in CR_REF_RE.findall(rec.body))
        return [pool[c] for c in sorted(referenced - have) if c in pool]

    @staticmethod
    def _insert_payload(html: bytes, payload: dict, *, at_top: bool) -> bytes:
        blob = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
        tag = (f'<script type="application/json" data-content-len="{len(blob)}" '
               f'data-sjs>{blob}</script>').encode("utf-8")
        if at_top:
            m = re.search(rb"<body[^>]*>", html)
            if m:
                return html[:m.end()] + tag + html[m.end():]
        i = html.rfind(b"</body>")
        return html + tag if i == -1 else html[:i] + tag + html[i:]

    # -- output ----------------------------------------------------------
    REPAIRS = ("sjs", "resources", "translations", "routes", "posts", "documents")

    def run(self, skip: Iterable[str] = ()) -> None:
        skip = set(skip)
        self.analyze()
        if "sjs" not in skip:
            self.repair_data_sjs_lengths()
        if "resources" not in skip:
            self.repair_missing_resources()
        if "translations" not in skip:
            self.repair_translations()
            self.repair_referenced_translations()
        if "routes" not in skip:
            self.repair_route_definitions()
        if "posts" not in skip:
            self.repair_post_aliases()
        if "documents" not in skip:
            self.repair_documents(skip)

    def to_har(self, path: Path) -> Path:
        entries = []
        for r in self.records + self.added:
            entry = {
                "startedDateTime": r.ts or "2025-01-01T00:00:00.000Z",
                "request": {"method": r.method, "url": r.url,
                            "headers": r.req_headers},
                "response": {
                    "status": r.status, "statusText": "OK",
                    "headers": r.headers or [{"name": "content-type", "value": r.mime}],
                    "content": {"mimeType": r.mime or "application/octet-stream",
                                "encoding": "base64",
                                "text": base64.b64encode(r.body).decode("ascii")},
                },
            }
            if r.post_body is not None:
                entry["request"]["postData"] = {
                    "text": r.post_body.decode("utf-8", "replace")}
            entries.append(entry)
        har = {"log": {"version": "1.2",
                       "creator": {"name": "wacz_repair", "version": "1"},
                       "entries": entries}}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(har, fh)
        return path

    def report_markdown(self, input_path: Path, output_path: Path) -> str:
        lines = [
            "# WACZ repair report", "",
            f"* Input: `{input_path}`",
            f"* Output: `{output_path}`",
            f"* Records in input: {len(self.records)}",
            f"* Records added: {len(self.added)}",
            "",
            "All modifications below concern code loading, Meta's own interface "
            "string tables, and request/response bookkeeping. Archived page "
            "content - posts, captions, usernames, counts, comments and media - "
            "is carried over byte for byte and is never synthesised or "
            "re-attributed.", "",
            "| # | Intervention | Target | Source | Reason |",
            "|---|---|---|---|---|",
        ]
        for i, e in enumerate(self.report, 1):
            def cell(s: str) -> str:
                s = str(s).replace("|", "\\|")
                return s if len(s) < 160 else s[:157] + "..."
            lines.append(f"| {i} | {cell(e['kind'])} | `{cell(e['target'])}` | "
                         f"{cell(e['source'])} | {cell(e['reason'])} |")
        return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--donor", type=Path, action="append", default=[],
                    help="another capture of the same site, used only to supply "
                         "resources missing from the input")
    ap.add_argument("--report", type=Path, help="write a Markdown modification report")
    ap.add_argument("--allow-network", action="store_true",
                    help="permit fetching missing static resources from the live CDN "
                         "or the Wayback Machine")
    ap.add_argument("--no-cross-build", action="store_true",
                    help="do not substitute a resource with the same logical resource "
                         "from another build")
    ap.add_argument("--skip", default="",
                    help="comma-separated repairs to skip: "
                         "sjs,resources,translations,routes,posts,documents,maps,preload,defines")
    ap.add_argument("--dry-run", action="store_true",
                    help="analyse and report, but do not write a repaired archive")
    args = ap.parse_args(argv)

    out = args.output or args.input.with_name(args.input.stem + "-repaired.wacz")
    print(f"[wacz_repair] reading {args.input}")
    records = load_wacz(args.input, provenance="capture")
    print(f"[wacz_repair] {len(records)} records")
    donors: list[Record] = []
    for d in args.donor:
        print(f"[wacz_repair] reading donor {d}")
        donors += load_wacz(d, provenance=f"donor:{d.name}", code_only=True)
    if donors:
        print(f"[wacz_repair] {len(donors)} donor records")

    rep = WaczRepairer(records, donors, allow_network=args.allow_network,
                       allow_cross_build=not args.no_cross_build)
    rep.run([s for s in args.skip.split(',') if s])
    print(f"[wacz_repair] {len(rep.report)} interventions, {len(rep.added)} records added")
    for e in rep.report:
        print(f"  - {e['kind']}: {e['target'][:90]}")

    if args.report:
        args.report.write_text(rep.report_markdown(args.input, out), encoding="utf-8")
        print(f"[wacz_repair] report written to {args.report}")
    if args.dry_run:
        return 0

    har_path = out.with_suffix(".repair.har")
    rep.to_har(har_path)
    generate_wacz(har_path, out, primary_page_url(args.input))
    try:
        har_path.unlink()
    except OSError:
        pass
    print(f"[wacz_repair] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
