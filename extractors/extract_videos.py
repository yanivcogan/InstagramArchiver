import base64
import html
import json
import os
import re
import subprocess
import traceback
from hashlib import md5
from pathlib import Path
from typing import Optional, Literal
from urllib import parse as urllib_parse

import ijson
import requests
from pydantic import BaseModel, field_validator

from archiver.summarizers import download_log as dl
from extractors.instagram.models import VideoVersion
from extractors.structures_extraction import StructureType, opened_post_structures, structures_from_har


def _safe_id(identifier: str, max_len: int = 60) -> str:
    """Return identifier truncated to max_len, using an md5 suffix to stay unique."""
    if len(identifier) <= max_len:
        return identifier
    return identifier[:max_len - 9] + '_' + md5(identifier.encode()).hexdigest()[:8]
from extractors.instagram.structures_extraction_api_v1 import ApiV1Response
from extractors.instagram.structures_extraction_graphql import GraphQLResponse
from extractors.instagram.structures_extraction_html import PageResponse
from extractors.threads.structures_extraction import ThreadsResponse
from utils.integrity import FileIntegrity, protect_file, protect_file_best_effort, prune_orphan_sidecars

OnLoggedMissingVideo = Literal["reassemble_from_har_only", "skip", "redownload"]


class MediaSegment(BaseModel):
    start: Optional[int]
    end: Optional[int]
    data: bytes


class MediaTrack(BaseModel):
    base_url: str
    full_url: str
    segments: list[MediaSegment]


class Video(BaseModel):
    xpv_asset_id: str
    fetched_tracks: Optional[dict[str, MediaTrack]]
    full_asset: Optional[str] = None
    # Every directly-downloadable URL for this asset, highest-quality first:
    # all video_versions plus every DASH manifest <BaseURL> representation.
    # download_full_asset tries them in order (validating each) so a single
    # transient CDN failure doesn't force a fall back to lossy HAR reassembly,
    # and so DASH-delivered videos (whose video_versions[0] may fail while a
    # manifest BaseURL succeeds) still get a full-quality file. full_asset stays
    # the canonical URL used for entity linking; candidates only drive download.
    full_asset_candidates: Optional[list[str]] = None
    cover_photo_url: Optional[str] = None
    local_files: Optional[list[Path]] = None
    # True when a .mp4 request for this asset appears in the HAR, even if the
    # response body wasn't captured. fetched_tracks alone can't carry this:
    # Threads streams video as open-ended bytes=0- responses consumed by the
    # media pipeline, so a watched video has a request in the HAR but no track.
    # Used to distinguish "viewed but body uncaptured" from genuinely unfetched
    # media (a post that was never opened).
    requested_in_session: bool = False

    @field_validator('xpv_asset_id', mode='before')
    @classmethod
    def coerce_to_str(cls, v):
        return str(v) if v is not None else v


def extract_xpv_asset_id(url) -> Optional[str]:
    # Parse query string
    parsed_url = urllib_parse.urlparse(url)
    query_params = urllib_parse.parse_qs(parsed_url.query)

    # Get the `efg` parameter (it may be URL-encoded)
    efg_encoded = query_params.get('efg')
    if not efg_encoded:
        try:
            return str(int(md5(url.split(".mp4")[0].split("/")[-1].encode("utf-8")).hexdigest(), 16))
        except Exception:
            return None

    # Base64-decode the efg value
    try:
        efg_json = base64.urlsafe_b64decode(efg_encoded[0] + '==')  # Add padding if missing
        efg_data = json.loads(efg_json.decode('utf-8'))
        xpv_asset_id = efg_data.get('xpv_asset_id')
        if not xpv_asset_id:
            raise ValueError("xpv_asset_id not found in efg data")
        return str(xpv_asset_id)
    except Exception as e:
        print(f"Error decoding efg: {e}")
        return None


def extract_xpv_asset_id_from_dash_manifest(manifest_xml: str) -> Optional[str]:
    """Try to get xpv_asset_id from the efg param of any BaseURL in a DASH manifest.

    DASH manifests are XML and use HTML entities (e.g. &amp; for &) in URLs.
    We must HTML-decode each BaseURL before URL-parsing so that query parameter
    names like 'efg' are found correctly (raw XML has 'amp;efg' as the key).
    """
    for base_url in re.findall(r'<BaseURL>([^<]+)</BaseURL>', manifest_xml):
        result = extract_xpv_asset_id(html.unescape(base_url))
        if result:
            return result
    return None


def dash_manifest_base_urls(manifest_xml: str) -> list[str]:
    """Return the video <BaseURL>s of a DASH manifest, highest-bandwidth first.

    These are directly-downloadable per-representation URLs. Instagram serves the
    same carousel video either as a progressive file (video_versions with
    stp=dst-mp4) or as DASH (video_versions are t2 streaming renditions plus a
    manifest); in the DASH case the manifest BaseURLs are the reliable full-asset
    download sources.

    Only video/mp4 Representations are returned — a DASH manifest also carries an
    audio-only AdaptationSet, and an audio BaseURL would pass ffprobe validation
    and be wrongly accepted as the "full asset" instead of falling through to
    HAR-segment reassembly. If no Representation declares a mimeType (unusual),
    fall back to every BaseURL so a malformed manifest doesn't drop all candidates.
    """
    video: list[tuple[int, str]] = []
    saw_mime = False
    for rep in re.findall(r'<Representation\b[^>]*>.*?</Representation>', manifest_xml, re.DOTALL):
        head = rep[:rep.find('>') + 1]
        mime_m = re.search(r'mimeType=["\']([^"\']+)["\']', head)
        if mime_m:
            saw_mime = True
            if not mime_m.group(1).startswith('video'):
                continue
        bw_m = re.search(r'bandwidth=["\'](\d+)["\']', head)
        bandwidth = int(bw_m.group(1)) if bw_m else 0
        for raw in re.findall(r'<BaseURL>([^<]+)</BaseURL>', rep):
            url = html.unescape(raw).strip()
            if url:
                video.append((bandwidth, url))
    if video:
        video.sort(key=lambda bw_url: -bw_url[0])
        return [url for _, url in video]
    if saw_mime:
        # mimeType was present but no video representation matched — nothing to add.
        return []
    # No mimeType info at all: best-effort, return every BaseURL (legacy behaviour).
    return [html.unescape(b).strip() for b in re.findall(r'<BaseURL>([^<]+)</BaseURL>', manifest_xml) if b.strip()]


def dedup_urls_by_filename(urls: list[Optional[str]]) -> list[str]:
    """Deduplicate a URL list by content-addressed filename, preserving first-seen order.

    The filename (path segment before ".mp4") is stable across the query params/CDN
    hosts that differ between a video_versions URL and the DASH BaseURL for the same
    representation, so it is the right dedup key for the same physical rendition.
    """
    ordered: list[str] = []
    seen_filenames: set[str] = set()
    for url in urls:
        if not url:
            continue
        filename = url.split('.mp4')[0].split('/')[-1]
        if not filename or filename in seen_filenames:
            continue
        seen_filenames.add(filename)
        ordered.append(url)
    return ordered


def full_asset_candidate_urls(
        versions: Optional[list[VideoVersion]],
        manifest: Optional[str],
) -> list[str]:
    """Ordered, filename-deduplicated list of every full-asset URL for a video.

    video_versions come first (Instagram orders them highest-quality-first), then
    any DASH manifest BaseURL not already represented.
    """
    urls: list[Optional[str]] = [vv.url for vv in (versions or [])]
    if manifest and isinstance(manifest, str):
        urls.extend(dash_manifest_base_urls(manifest))
    return dedup_urls_by_filename(urls)


# ---------------------------------------------------------------------------
# Shared video-segment accumulation and key-reconciliation helpers.
# Used by extract_video_maps, _scan_har_once, and scan_wacz so that all three
# scanners apply identical cascade logic and remain easy to keep in sync.
# ---------------------------------------------------------------------------

def _normalize_mp4_url(url: str) -> str:
    """Strip bytestart/byteend query params from a CDN .mp4 URL."""
    parsed = urllib_parse.urlparse(url)
    query = '&'.join(
        f"{k}={v[0]}" if len(v) == 1 else '&'.join(f"{k}={i}" for i in v)
        for k, v in urllib_parse.parse_qs(parsed.query).items()
        if k not in ('bytestart', 'byteend')
    )
    return str(urllib_parse.urlunparse(parsed._replace(query=query)))


def _parse_byte_range(url: str) -> tuple[Optional[int], Optional[int]]:
    """Return (bytestart, byteend) from URL query params, or (None, None)."""
    start = int(url.split('bytestart=')[1].split('&')[0]) if 'bytestart=' in url else None
    end = int(url.split('byteend=')[1].split('&')[0]) if 'byteend=' in url else None
    return start, end


def _parse_content_range(value: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """Parse a response ``Content-Range`` header (e.g. ``bytes 10334554-16803910/16803911``)
    into an inclusive (start, end), or (None, None)."""
    if not value:
        return None, None
    m = re.search(r'bytes\s+(\d+)-(\d+)', value)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _parse_range_header(value: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """Parse a request ``Range`` header (e.g. ``bytes=10334554-`` or ``bytes=0-1023``)
    into an inclusive (start, end); end is None for an open-ended range."""
    if not value:
        return None, None
    m = re.search(r'bytes=(\d+)-(\d*)', value)
    if not m:
        return None, None
    return int(m.group(1)), (int(m.group(2)) if m.group(2) else None)


def _header_value(headers: list, name: str) -> Optional[str]:
    name = name.lower()
    for h in headers or []:
        if h.get('name', '').lower() == name:
            return h.get('value')
    return None


def byte_range_from_har_entry(entry: dict) -> tuple[Optional[int], Optional[int]]:
    """Recover a media segment's byte offset from a HAR entry's HTTP headers.

    Instagram encodes the range in the URL (``bytestart``/``byteend``), but
    Threads/Barcelona uses standard HTTP ranged requests: the offset lives in the
    response ``Content-Range`` (authoritative — it states exactly which bytes the
    body covers) and, failing that, the request ``Range`` header. Without this the
    body of a tail request (e.g. ``bytes 10334554-…``) would be misfiled at offset
    0, corrupting the reassembled file.
    """
    cr = _parse_content_range(_header_value(entry.get('response', {}).get('headers', []), 'content-range'))
    if cr[0] is not None:
        return cr
    return _parse_range_header(_header_value(entry.get('request', {}).get('headers', []), 'range'))


def accumulate_video_segment(
    url: str,
    body: bytes,
    real_xpv_dict: dict[str, Video],
    fallback_dict: dict[str, Video],
    filename_to_xpv: dict[str, str],
    byte_range: Optional[tuple[Optional[int], Optional[int]]] = None,
) -> None:
    """
    Process one .mp4 URL+body and route it into the appropriate accumulation dict.

    Cascade step 1 — extract xpv_asset_id from URL efg:
    - Found: add segment to real_xpv_dict[xpv_asset_id]; record
      filename_to_xpv[filename] = xpv_asset_id for later reconciliation.
    - Not found: add segment to fallback_dict[filename].

    The filename component of Instagram CDN URLs (path segment before ".mp4") is
    content-addressed and identical across video_versions URLs and DASH manifest
    BaseURLs for the same video, making it a reliable reconciliation anchor.

    The segment's byte offset comes from the URL (``bytestart``/``byteend``, the
    Instagram convention); when absent there, callers pass ``byte_range`` recovered
    from the HTTP ``Content-Range``/``Range`` headers (the Threads convention) so
    tail ranges land at the correct offset instead of being misfiled at byte 0.

    Call reconcile_video_dicts() after all entries have been accumulated to resolve
    fallback entries using structure DASH manifests (cascade steps 2-3).
    """
    base_url = url.split('.mp4')[0]
    filename = base_url.split('/')[-1]
    if not filename:
        return
    full_url = _normalize_mp4_url(url)
    start, end = _parse_byte_range(url)
    if start is None and end is None and byte_range is not None:
        start, end = byte_range
    xpv_asset_id = extract_xpv_asset_id(url)

    if xpv_asset_id:
        filename_to_xpv[filename] = xpv_asset_id
        target: dict[str, Video] = real_xpv_dict
        key: str = xpv_asset_id
    else:
        target = fallback_dict
        key = filename

    if key not in target:
        target[key] = Video(xpv_asset_id=key, fetched_tracks={})
    fetched_tracks = target[key].fetched_tracks
    if fetched_tracks is not None:
        if filename not in fetched_tracks:
            fetched_tracks[filename] = MediaTrack(base_url=base_url, full_url=full_url, segments=[])
        fetched_tracks[filename].segments.append(MediaSegment(start=start, end=end, data=body))


def _build_filename_xpv_map(structures: list[StructureType]) -> dict[str, str]:
    """
    Derive the canonical xpv_asset_id for each media item in structures and
    map ALL of its video_versions filenames to that ID.

    Unlike extract_videos_from_structures (which only exposes video_versions[0]
    as full_asset), this covers every quality level the browser may have fetched.
    Used by reconcile_video_dicts and the re-keying pass in acquire_videos so
    that fallback_dict entries are resolved even when the browser chose a
    non-first quality variant.
    """
    result: dict[str, str] = {}
    seen_pks: set[str] = set()

    def _process(
        versions: Optional[list[VideoVersion]],
        manifest: Optional[str],
        pk: Optional[str],
    ) -> None:
        if not versions or not pk:
            return
        pk_str = str(pk)
        if pk_str in seen_pks:
            return
        seen_pks.add(pk_str)
        first_url = versions[0].url
        if not first_url:
            return
        xpv: Optional[str] = extract_xpv_asset_id(first_url)
        if manifest:
            dash_id = extract_xpv_asset_id_from_dash_manifest(manifest)
            if dash_id:
                xpv = dash_id
        if not xpv:
            xpv = pk_str
        for vv in versions:
            if vv.url:
                fn = vv.url.split('.mp4')[0].split('/')[-1]
                if fn and fn not in result:
                    result[fn] = xpv

    for s in structures:
        if isinstance(s, GraphQLResponse):
            if s.reels_media:
                for edge in s.reels_media.edges:
                    for item in edge.node.items:
                        _process(item.video_versions, getattr(item, 'video_dash_manifest', None), item.pk)
                        for ci in (item.carousel_media or []):
                            _process(ci.video_versions, getattr(ci, 'video_dash_manifest', None), ci.pk)
            if s.stories_feed:
                for edge in s.stories_feed.reels_media:
                    for item in edge.items:
                        _process(item.video_versions, getattr(item, 'video_dash_manifest', None), item.pk)
                        for ci in (item.carousel_media or []):
                            _process(ci.video_versions, getattr(ci, 'video_dash_manifest', None), ci.pk)
            if s.profile_timeline:
                for edge in s.profile_timeline.edges:
                    _process(edge.node.video_versions, getattr(edge.node, 'video_dash_manifest', None), edge.node.pk)
                    for ci in (edge.node.carousel_media or []):
                        _process(ci.video_versions, getattr(ci, 'video_dash_manifest', None), ci.pk)
            if s.clips_user_connection:
                for edge in s.clips_user_connection.edges:
                    m = edge.node.media
                    _process(m.video_versions, getattr(m, 'video_dash_manifest', None), m.pk)
            if s.post_shortcode:
                for post in s.post_shortcode.items:
                    _process(post.video_versions, getattr(post, 'video_dash_manifest', None), post.pk)
                    for ci in (post.carousel_media or []):
                        _process(ci.video_versions, getattr(ci, 'video_dash_manifest', None), ci.pk)
        elif isinstance(s, ApiV1Response):
            if s.media_info:
                for item in s.media_info.items:
                    _process(item.video_versions, getattr(item, 'video_dash_manifest', None), item.pk)
                    for ci in (item.carousel_media or []):
                        _process(ci.video_versions, getattr(ci, 'video_dash_manifest', None), ci.pk)
        elif isinstance(s, PageResponse):
            if s.posts:
                for post in s.posts.items:
                    _process(post.video_versions, getattr(post, 'video_dash_manifest', None), post.pk)
                    for ci in (post.carousel_media or []):
                        _process(ci.video_versions, getattr(ci, 'video_dash_manifest', None), ci.pk)
            if s.stories:
                for edge in s.stories.edges:
                    for item in edge.node.items:
                        _process(item.video_versions, getattr(item, 'video_dash_manifest', None), item.pk)
                        for ci in (item.carousel_media or []):
                            _process(ci.video_versions, getattr(ci, 'video_dash_manifest', None), ci.pk)
            if s.highlight_reels:
                for reel in s.highlight_reels.edges:
                    for item in reel.node.items:
                        _process(item.video_versions, getattr(item, 'video_dash_manifest', None), item.pk)
                        for ci in (item.carousel_media or []):
                            _process(ci.video_versions, getattr(ci, 'video_dash_manifest', None), ci.pk)
            if s.stories_direct:
                for story in s.stories_direct.reels_media:
                    for item in story.items:
                        _process(item.video_versions, getattr(item, 'video_dash_manifest', None), item.pk)
                        for ci in (item.carousel_media or []):
                            _process(ci.video_versions, getattr(ci, 'video_dash_manifest', None), ci.pk)
            if s.timelines:
                for item in s.timelines.items:
                    _process(item.video_versions, getattr(item, 'video_dash_manifest', None), item.pk)
                    for ci in (item.carousel_media or []):
                        _process(ci.video_versions, getattr(ci, 'video_dash_manifest', None), ci.pk)
        elif isinstance(s, ThreadsResponse):
            for post in s.posts:
                _process(post.video_versions, getattr(post, 'video_dash_manifest', None), post.pk)
                for ci in (post.carousel_media or []):
                    _process(ci.video_versions, getattr(ci, 'video_dash_manifest', None), ci.pk)

    return result


def reconcile_video_dicts(
    real_xpv_dict: dict[str, Video],
    fallback_dict: dict[str, Video],
    filename_to_xpv: dict[str, str],
    structures: Optional[list[StructureType]] = None,
) -> dict[str, Video]:
    """
    Merge fallback_dict into real_xpv_dict, resolving filename-keyed entries.

    Cascade steps 2-3:
    2. If structures are provided, enrich filename_to_xpv by mapping ALL
       video_versions filenames for each structure video to its canonical
       xpv_asset_id (cascades through URL efg → DASH manifest → post pk).
       Covers all quality levels the browser may have fetched, not just
       video_versions[0].
    3. For each fallback entry keyed by filename:
       - Resolved: if the canonical entry already exists in real_xpv_dict, merge
         its tracks in; otherwise re-key the video with the canonical id.
       - Unresolved: insert under the filename key — no data is lost; the video
         can still be assembled/downloaded if needed.

    Returns real_xpv_dict (mutated in place).
    """
    # Step 2: enrich filename_to_xpv from ALL video_versions filenames in structures
    if structures:
        struct_map = _build_filename_xpv_map(structures)
        for fn, xpv in struct_map.items():
            if fn not in filename_to_xpv:
                filename_to_xpv[fn] = xpv

    # Step 3: resolve and merge fallback entries
    for fn, video in fallback_dict.items():
        real_xpv = filename_to_xpv.get(fn)
        if real_xpv:
            if real_xpv in real_xpv_dict:
                existing_tracks = real_xpv_dict[real_xpv].fetched_tracks
                if existing_tracks is not None:
                    for track_name, track in (video.fetched_tracks or {}).items():
                        if track_name not in existing_tracks:
                            existing_tracks[track_name] = track
            else:
                real_xpv_dict[real_xpv] = video.model_copy(update={'xpv_asset_id': real_xpv})
        else:
            real_xpv_dict[fn] = video  # unresolved — keep as filename-keyed, data not lost

    return real_xpv_dict


def extract_video_maps(har_path: Path) -> list[Video]:
    """
    Extracts video segment data from the HAR file using streaming JSON parsing.

    Applies cascade step 1 (URL efg) per entry and step 2 (filename_to_xpv
    built from sibling DASH-segment requests) at the end. Structures are not
    available here; acquire_videos performs the final step-2 enrichment using
    the structures_videos it already computes.
    """
    real_xpv_dict: dict[str, Video] = {}
    fallback_dict: dict[str, Video] = {}
    filename_to_xpv: dict[str, str] = {}

    with open(har_path, 'rb') as file:
        for entry in ijson.items(file, 'log.entries.item'):
            try:
                if '.mp4' in entry['request']['url'] and 'text' in entry['response']['content']:
                    url = entry['request']['url']
                    body = base64.b64decode(entry['response']['content']['text'])
                    accumulate_video_segment(url, body, real_xpv_dict, fallback_dict, filename_to_xpv,
                                             byte_range=byte_range_from_har_entry(entry))
            except Exception as e:
                print(f'Error processing entry: {e}')
                traceback.print_exc()
                continue

    # Reconcile without structures; acquire_videos does a second pass with structures.
    return list(reconcile_video_dicts(real_xpv_dict, fallback_dict, filename_to_xpv).values())


def _count_complete_trun_samples(raw_data: bytes) -> Optional[int]:
    """
    Parse a raw fMP4 byte string and return the number of trun samples that fit
    entirely within the available mdat bytes.

    Returns None when:
    - the file is not truncated (all samples available), OR
    - parsing fails (caller should proceed without -frames:v).
    Returns an integer >= 0 indicating how many complete samples exist.
    """
    import struct

    def _iter_boxes(data: bytes, start: int, end: int):
        pos = start
        while pos + 8 <= end:
            size = struct.unpack_from('>I', data, pos)[0]
            btype = data[pos + 4:pos + 8].decode('latin-1', errors='replace')
            if size == 0:
                yield btype, pos, len(data), pos + 8
                break
            elif size == 1:
                if pos + 16 > end:
                    break
                size = struct.unpack_from('>Q', data, pos + 8)[0]
                yield btype, pos, pos + size, pos + 16
            else:
                yield btype, pos, pos + size, pos + 8
            if size < 8:
                break
            pos += size

    # Locate mdat and measure truncation
    mdat_data_start = None
    mdat_claimed_end = None
    for btype, bstart, bend, dstart in _iter_boxes(raw_data, 0, len(raw_data)):
        if btype == 'mdat':
            mdat_data_start = dstart
            mdat_claimed_end = bend
            break

    if mdat_data_start is None:
        return None

    available = len(raw_data) - mdat_data_start
    claimed = mdat_claimed_end - mdat_data_start
    if available >= claimed:
        return None  # file is complete

    # Locate moof → traf → trun
    trun_payload: Optional[bytes] = None
    for btype, bstart, bend, dstart in _iter_boxes(raw_data, 0, len(raw_data)):
        if btype == 'moof':
            for inner_type, _, inner_end, inner_dstart in _iter_boxes(raw_data, dstart, bend):
                if inner_type == 'traf':
                    for t2_type, _, t2_end, t2_dstart in _iter_boxes(raw_data, inner_dstart, inner_end):
                        if t2_type == 'trun':
                            trun_payload = raw_data[t2_dstart:t2_end]
                            break
                if trun_payload is not None:
                    break
            break

    if not trun_payload or len(trun_payload) < 8:
        return None

    # Parse trun full-box header: version(1) + flags(3) + sample_count(4)
    flags = (trun_payload[1] << 16) | (trun_payload[2] << 8) | trun_payload[3]
    sample_count = struct.unpack_from('>I', trun_payload, 4)[0]

    if not (flags & 0x200):
        # sample_size not present per-sample — need trex default, can't determine easily
        return None

    pos = 8
    if flags & 0x001:  # data_offset_present
        pos += 4
    if flags & 0x004:  # first_sample_flags_present
        pos += 4

    cumulative = 0
    for i in range(sample_count):
        if flags & 0x100:
            if pos + 4 > len(trun_payload):
                return i
            pos += 4
        # sample_size (flags & 0x200 is guaranteed above)
        if pos + 4 > len(trun_payload):
            return i
        size = struct.unpack_from('>I', trun_payload, pos)[0]
        pos += 4
        if flags & 0x400:
            if pos + 4 > len(trun_payload):
                return i
            pos += 4
        if flags & 0x800:
            if pos + 4 > len(trun_payload):
                return i
            pos += 4

        if cumulative + size > available:
            return i  # this sample is incomplete; i samples are complete
        cumulative += size

    return None  # all samples fit


def clean_segments(files_to_delete):
    for file in files_to_delete:
        if os.path.exists(file):
            os.remove(file)
        else:
            print(f"File {file} does not exist, skipping deletion.")

def clean_corrupted_files(path_to_check: Path) -> bool:
    if not os.path.exists(path_to_check):
        print(f"File {path_to_check} does not exist, skipping check.")
        return False
    if os.path.getsize(path_to_check) < 1000:
        os.remove(path_to_check)
        return False
    try:
        # Use ffprobe to check if the file is a valid media file
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration,format_name', '-select_streams', 'v:0',
             '-show_entries', 'stream=codec_name', '-of', 'default=noprint_wrappers=1:nokey=1', path_to_check],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
    except Exception as e:
        # ffprobe could not be run at all (e.g. not installed / not on PATH for
        # this process — the incorporation pipeline does not run
        # ensure_ffmpeg_installed()). "Cannot validate" is NOT evidence of
        # corruption, so keep the reassembled file rather than deleting a good
        # asset. Mirrors downloaded_full_asset_is_acceptable's tolerance.
        print(f"ffprobe unavailable, keeping file without validation: {path_to_check}: {e}")
        return True
    if result.returncode != 0 or not result.stdout.strip():
        os.remove(path_to_check)  # ffprobe ran and found the file corrupt
        return False
    return True


def downloaded_full_asset_is_acceptable(path: Path) -> bool:
    """Whether a freshly-downloaded full-asset file should be accepted.

    Returns False only on POSITIVE evidence the file is unusable: missing, absurdly
    small (< 1000 bytes, i.e. an error page), or ffprobe definitively rejecting it.
    When ffprobe cannot run at all (not installed / spawn error), returns True —
    before candidate validation existed, download_full_asset trusted any HTTP-200
    body, so an unavailable ffprobe must not turn a working full-asset fetch into a
    dropped video. Unlike clean_corrupted_files this never deletes the file (the
    caller owns cleanup) and never deletes on a can't-run error.
    """
    try:
        if not path.exists() or path.stat().st_size < 1000:
            return False
    except OSError:
        return False
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration,format_name',
             '-select_streams', 'v:0', '-show_entries', 'stream=codec_name', '-of',
             'default=noprint_wrappers=1:nokey=1', str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
    except Exception as e:
        print(f"ffprobe unavailable, accepting full-asset download without validation: {e}")
        return True
    return result.returncode == 0 and bool(result.stdout.strip())

def merge_video_and_audio_tracks(video_path: Path, audio_path: Path, output_path: Path) -> bool:
    """Merge video and audio tracks into a single file."""
    try:
        # Use ffmpeg to merge video and audio
        subprocess.run(
            ['ffmpeg', '-y', '-i', video_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac', '-strict',
             'experimental',
             output_path],
            check=True
        )
        # Check if the merge was successful
        if os.path.exists(output_path):
            print(f"Merged video and audio into {output_path}")
            clean_segments([video_path, audio_path])
            return True
        else:
            print(f"Failed to create merged file at {output_path}")
            return False
    except subprocess.CalledProcessError as e:
        print(f"Error merging video and audio: {e}")
        return False

def download_file(url: str, attempts: int = 1) -> Optional[bytes]:
    # attempts > 1 retries transient failures (timeouts, 5xx, connection resets).
    # Instagram CDN GETs occasionally fail transiently; a single miss must not be
    # enough to abandon a full-asset URL and drop to lossy reassembly.
    for attempt in range(1, max(1, attempts) + 1):
        try:
            print("Downloading file from:", url, f"(attempt {attempt}/{max(1, attempts)})" if attempts > 1 else "")
            resp = requests.get(url)
            if resp.status_code == 200:
                return resp.content
            raise Exception(f"Failed to download file, status code: {resp.status_code}")
        except Exception as e:
            print(f"Error: {e}")
    return None

class AssetSaveResult(BaseModel):
    success: bool = True
    location: Optional[Path] = None
    integrity: Optional[FileIntegrity] = None

def save_fetched_asset(video: Video, output_dir: Path, download_full_track: bool) -> AssetSaveResult:
    temp_video_file: Optional[Path] = None
    temp_audio_file: Optional[Path] = None
    merged_file: Optional[Path] = None
    xpv_asset_id = video.xpv_asset_id
    for track_name, track in video.fetched_tracks.items():
        track_data: Optional[bytes] = None
        download_type: Optional[Literal["har_segments", "full_track"]] = None
        if download_full_track:
            # Download the full track as a single file
            track_data = download_file(track.full_url)
            if track_data is not None:
                print("Downloaded full track data for", track_name)
                download_type = "full_track"
        if track_data is None:
            # Sort segments by start byte (byteend in CDN URLs is the last inclusive byte).
            track.segments.sort(key=lambda s: s.start if s.start is not None else 0)

            # Find the contiguous coverage from byte 0. If the video was not played to
            # the end, later byte ranges will be absent, leaving holes. Truncating at the
            # last contiguous byte avoids zero-filled gaps that would corrupt the container.
            contiguous_end = 0
            for segment in track.segments:
                seg_start = segment.start if segment.start is not None else 0
                # byteend is inclusive, so the exclusive Python end is end+1
                seg_end = (segment.end + 1) if segment.end is not None else (seg_start + len(segment.data))
                if seg_start <= contiguous_end:
                    contiguous_end = max(contiguous_end, seg_end)
                else:
                    break  # gap in coverage — stop here

            if contiguous_end == 0:
                download_type = "har_segments"
                track_data = b''
            else:
                track_data = bytearray(contiguous_end)
                for segment in track.segments:
                    if segment.start is None:
                        track_data = bytearray(segment.data)
                        break
                    seg_start = segment.start
                    seg_end = (segment.end + 1) if segment.end is not None else (seg_start + len(segment.data))
                    if seg_start >= contiguous_end:
                        break
                    actual_end = min(seg_end, contiguous_end)
                    track_data[seg_start:actual_end] = segment.data[:actual_end - seg_start]
                download_type = "har_segments"

        source_type = "har_segments" if download_type == "har_segments" else "full_track"
        single_track_file = f"track_{_safe_id(xpv_asset_id)}_{_safe_id(track_name)}_{source_type}.mp4"
        if track_data is not None and len(track_data) > 0:
            with open(output_dir / single_track_file, 'wb') as f:
                f.write(track_data)

        # For partial fMP4 files (truncated DASH segments), the moov atom declares the
        # full duration but the mdat is cut short, causing players to reject the file.
        # Re-muxing with ffmpeg -c copy rewrites the duration to match actual content.
        raw_path = output_dir / single_track_file
        if raw_path.exists() and raw_path.stat().st_size > 0:
            recovered_path = output_dir / f"_recovered_{single_track_file}"
            try:
                n_complete = _count_complete_trun_samples(bytes(track_data) if track_data else b'')
                frames_args = ['-frames:v', str(n_complete)] if n_complete is not None and n_complete > 0 else []
                result = subprocess.run(
                    ['ffmpeg', '-y', '-i', str(raw_path), '-c', 'copy'] + frames_args + [str(recovered_path)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                if recovered_path.exists() and recovered_path.stat().st_size > 0:
                    os.replace(str(recovered_path), str(raw_path))
                    print(f"Recovered partial video ({n_complete or 'all'} samples): {single_track_file}")
            except Exception as e:
                print(f"ffmpeg recovery failed for {single_track_file}: {e}")
            finally:
                if recovered_path.exists():
                    try:
                        os.remove(recovered_path)
                    except Exception:
                        pass

        valid_file = clean_corrupted_files(output_dir / single_track_file)
        if not valid_file:
            print(f"File {output_dir / single_track_file} is corrupted, skipping.")
            clean_segments([output_dir / single_track_file])
            continue

        if valid_file:
            # determine whether the file is audio or video using ffprobe
            try:
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=codec_type', '-of',
                     'default=noprint_wrappers=1:nokey=1',
                     str(output_dir / single_track_file)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                probe_stdout = result.stdout
            except Exception as e:
                # ffprobe not runnable — can't tell audio from video. Default to
                # treating the track as video (the common case) so the file is
                # still kept and linked rather than crashing the pipeline.
                print(f"ffprobe unavailable for audio/video detection, assuming video: {e}")
                probe_stdout = ""
            if 'audio' in probe_stdout:
                # keep track of the largest audio file
                new_file = output_dir / single_track_file
                if temp_audio_file is not None:
                    if os.path.getsize(new_file) > os.path.getsize(temp_audio_file):
                        temp_audio_file = new_file
                        # delete the smaller file
                        if os.path.exists(temp_audio_file):
                            os.remove(temp_audio_file)
                else:
                    temp_audio_file = new_file
            else:
                # keep track of the largest video file
                new_file = output_dir / single_track_file
                if temp_video_file is not None:
                    if os.path.getsize(new_file) > os.path.getsize(temp_video_file):
                        temp_video_file = new_file
                        # delete the smaller file
                        if os.path.exists(temp_video_file):
                            os.remove(temp_video_file)
                else:
                    temp_video_file = new_file

    if temp_audio_file is not None and temp_video_file is not None:
        merged_file_path = output_dir / f"xpv_{_safe_id(video.xpv_asset_id)}.mp4"
        merge_success = merge_video_and_audio_tracks(
            temp_video_file,
            temp_audio_file,
            merged_file_path
        )
        if merge_success:
            merged_file = merged_file_path

    most_complete_version = merged_file or temp_video_file or temp_audio_file or None

    if most_complete_version is None:
        print(f"No valid video segments found for xpv_asset_id {video.xpv_asset_id}.")
        return AssetSaveResult(success=False)

    # Best-effort protection: a PAR2/manifest failure must not discard a
    # successfully reassembled and ffprobe-validated media file (dropping it
    # would leave the media entity with a null local_url even though the asset
    # was captured). See protect_file_best_effort.
    return AssetSaveResult(
        success=True,
        location=most_complete_version,
        integrity=protect_file_best_effort(most_complete_version, output_dir),
    )


def extract_videos_from_structures(structures: list[StructureType]) -> list[Video]:
    # dict keyed by item pk → (video_versions, dash_manifest, item_pk, cover_photo_url)
    # item_pk is always the specific item's own pk (carousel_item.pk for carousels),
    # used as a last-resort fallback when no canonical xpv_asset_id can be extracted.
    pk_video_versions_dict: dict[str, tuple[list[VideoVersion], Optional[str], str, Optional[str]]] = dict()
    # Every downloadable full-asset URL seen for an item pk, accumulated across ALL
    # structures it appears in (a carousel item can show up in a GraphQL response
    # carrying a DASH manifest AND an API-v1/HTML response carrying only one URL).
    # Kept separate from pk_video_versions_dict so accumulating extra candidates does
    # NOT change which structure wins the canonical xpv_asset_id / full_asset (those
    # stay last-write-wins, exactly as before) — it only widens what
    # download_full_asset may try before falling back to reassembly.
    pk_candidate_urls: dict[str, list[str]] = dict()

    def _store(pk: Optional[str], versions: Optional[list[VideoVersion]], src: object) -> None:
        if not pk:
            return
        manifest: Optional[str] = getattr(src, 'video_dash_manifest', None)
        effective_versions = versions
        if not effective_versions and manifest and isinstance(manifest, str):
            for raw in re.findall(r'<BaseURL>([^<]+)</BaseURL>', manifest):
                url = html.unescape(raw).strip()
                if url:
                    effective_versions = [VideoVersion(url=url)]
                    break
        if not effective_versions:
            return
        cover_photo_url: Optional[str] = None
        iv2 = getattr(src, 'image_versions2', None)
        if iv2 and getattr(iv2, 'candidates', None):
            cover_photo_url = iv2.candidates[0].url
        pk_video_versions_dict[pk] = (effective_versions, manifest, pk, cover_photo_url)
        # Accumulate download candidates across every structure for this item (does
        # not affect the canonical key/full_asset chosen above).
        acc = pk_candidate_urls.setdefault(pk, [])
        acc.extend(vv.url for vv in effective_versions if vv.url)
        if manifest and isinstance(manifest, str):
            acc.extend(dash_manifest_base_urls(manifest))

    for s in structures:
        if isinstance(s, GraphQLResponse):
            if s.reels_media:
                for edge in s.reels_media.edges:
                    for item in edge.node.items:
                        _store(item.pk, item.video_versions, item)
                        if item.carousel_media:
                            for carousel_item in item.carousel_media:
                                _store(carousel_item.pk, carousel_item.video_versions, carousel_item)
            if s.stories_feed:
                for edge in s.stories_feed.reels_media:
                    for item in edge.items:
                        _store(item.pk, item.video_versions, item)
                        if item.carousel_media:
                            for carousel_item in item.carousel_media:
                                _store(carousel_item.pk, carousel_item.video_versions, carousel_item)
            if s.profile_timeline:
                for edge in s.profile_timeline.edges:
                    _store(edge.node.pk, edge.node.video_versions, edge.node)
                    if edge.node.carousel_media:
                        for carousel_item in edge.node.carousel_media:
                            _store(carousel_item.pk, carousel_item.video_versions, carousel_item)
            if s.clips_user_connection:
                for edge in s.clips_user_connection.edges:
                    _store(edge.node.media.pk, edge.node.media.video_versions, edge.node.media)
            if s.post_shortcode:
                for post in s.post_shortcode.items:
                    _store(post.pk, post.video_versions, post)
                    if post.carousel_media:
                        for carousel_item in post.carousel_media:
                            _store(carousel_item.pk, carousel_item.video_versions, carousel_item)
        elif isinstance(s, ApiV1Response):
            if s.media_info:
                for item in s.media_info.items:
                    _store(item.pk, item.video_versions, item)
                    if item.carousel_media:
                        for carousel_item in item.carousel_media:
                            _store(carousel_item.pk, carousel_item.video_versions, carousel_item)
        elif isinstance(s, PageResponse):
            if s.posts:
                for post in s.posts.items:
                    _store(post.pk, post.video_versions, post)
                    if post.carousel_media:
                        for carousel_item in post.carousel_media:
                            _store(carousel_item.pk, carousel_item.video_versions, carousel_item)
            if s.stories:
                for edge in s.stories.edges:
                    for item in edge.node.items:
                        _store(item.pk, item.video_versions, item)
                        if item.carousel_media:
                            for carousel_item in item.carousel_media:
                                _store(carousel_item.pk, carousel_item.video_versions, carousel_item)
            if s.highlight_reels:
                for reel in s.highlight_reels.edges:
                    for item in reel.node.items:
                        _store(item.pk, item.video_versions, item)
                        if item.carousel_media:
                            for carousel_item in item.carousel_media:
                                _store(carousel_item.pk, carousel_item.video_versions, carousel_item)
            if s.stories_direct:
                for story in s.stories_direct.reels_media:
                    for item in story.items:
                        _store(item.pk, item.video_versions, item)
                        if item.carousel_media:
                            for carousel_item in item.carousel_media:
                                _store(carousel_item.pk, carousel_item.video_versions, carousel_item)
            if s.timelines:
                for item in s.timelines.items:
                    _store(item.pk, item.video_versions, item)
                    if item.carousel_media:
                        for carousel_item in item.carousel_media:
                            _store(carousel_item.pk, carousel_item.video_versions, carousel_item)
        elif isinstance(s, ThreadsResponse):
            for post in s.posts:
                _store(post.pk, post.video_versions, post)
                if post.carousel_media:
                    for carousel_item in post.carousel_media:
                        _store(carousel_item.pk, carousel_item.video_versions, carousel_item)

    videos: dict[str, Video] = dict()
    for item_pk, (video_versions, dash_manifest, fallback_pk, cover_photo_url) in pk_video_versions_dict.items():
        first_url = video_versions[0].url
        if not first_url:
            continue
        try:
            xpv_asset_id = extract_xpv_asset_id(first_url)
            # video_versions efg may lack xpv_asset_id (e.g. clips/reels URLs).
            # DASH manifest BaseURLs carry the real xpv_asset_id — try those next.
            if dash_manifest:
                dash_id = extract_xpv_asset_id_from_dash_manifest(dash_manifest)
                if dash_id:
                    xpv_asset_id = dash_id
            # Last resort: use the item's own pk (unique per carousel item).
            if not xpv_asset_id:
                xpv_asset_id = fallback_pk
            # Candidates: this structure's own URLs first (so full_asset == first_url
            # leads and stays candidates[0] for both quality order and entity linking),
            # then any extra URLs accumulated from other structures for the same item.
            candidates = dedup_urls_by_filename(
                full_asset_candidate_urls(video_versions, dash_manifest)
                + pk_candidate_urls.get(fallback_pk, [])
            )
            video = Video(
                xpv_asset_id=xpv_asset_id,
                full_asset=first_url,
                full_asset_candidates=candidates,
                cover_photo_url=cover_photo_url,
                fetched_tracks=None
            )
            videos[xpv_asset_id] = video
        except Exception as e:
            print(f"Error extracting xpv_asset_id from video version URL {first_url}: {e}")
            continue
    return list(videos.values())


def get_existing_videos(working_dir: Path) -> dict[str, Path]:
    """Return a dict mapping filename stem (no .mp4) to Path for every .mp4 in working_dir."""
    result: dict[str, Path] = {}
    for file in working_dir.iterdir():
        if file.is_file() and file.suffix == '.mp4':
            stem = file.stem
            if stem not in result or file.stat().st_size > result[stem].stat().st_size:
                result[stem] = file
    return result


def download_full_asset(video: Video, output_dir: Path) -> AssetSaveResult:
    """Download the full asset, trying every known URL until one yields a valid file.

    Candidates are all video_versions plus every DASH manifest BaseURL (highest
    quality first). Each downloaded candidate is validated with ffprobe before it
    is accepted, so a truncated/garbage 200 response (or a video_versions URL that
    fails while a DASH BaseURL succeeds) transparently advances to the next URL
    instead of being kept — or forcing a fall back to lossy HAR reassembly.
    """
    # Prefer the explicit candidate list; fall back to the single canonical URL
    # for Videos built without candidates (e.g. HAR-only entries).
    candidates = list(video.full_asset_candidates or [])
    if video.full_asset and video.full_asset not in candidates:
        candidates.insert(0, video.full_asset)
    if not candidates:
        return AssetSaveResult(success=False)

    file_name = f"xpv_{_safe_id(video.xpv_asset_id)}_full.mp4"
    file_path = output_dir / file_name

    for url in candidates:
        try:
            download_result = download_file(url, attempts=3)
            if download_result is None:
                continue
            with open(file_path, 'wb') as f:
                f.write(download_result)
            # Validate before accepting so a truncated/garbage 200 advances to the next
            # candidate. Tolerant by design: only a definitive ffprobe rejection (or a
            # tiny file) is treated as invalid — if ffprobe can't run we accept, to
            # preserve the pre-validation behaviour of trusting a 200 response.
            if not downloaded_full_asset_is_acceptable(file_path):
                print(f"Full-asset candidate rejected (invalid/corrupt), trying next: {url}")
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                continue
            # Best-effort protection: a PAR2/manifest failure must not throw away
            # an accepted, on-disk full asset (see save_fetched_asset).
            integrity = protect_file_best_effort(file_path, output_dir)
            if video.cover_photo_url:
                try:
                    cover_data = download_file(video.cover_photo_url)
                    if cover_data:
                        ext = video.cover_photo_url.split('?')[0].rsplit('.', 1)[-1] or 'jpg'
                        cover_path = output_dir / f"xpv_{_safe_id(video.xpv_asset_id)}_cover.{ext}"
                        with open(cover_path, 'wb') as cf:
                            cf.write(cover_data)
                        protect_file(cover_path)
                except Exception as cover_err:
                    print(f"Warning: could not download cover photo for {video.xpv_asset_id}: {cover_err}")
            return AssetSaveResult(
                success=True,
                location=file_path,
                integrity=integrity,
            )
        except Exception as e:
            print(f"Error downloading full asset candidate {url}: {e}")
            continue

    print(f"All {len(candidates)} full-asset candidate(s) failed for {video.xpv_asset_id}.")
    return AssetSaveResult(success=False)


class VideoAcquisitionConfig(BaseModel):
    download_missing: bool = True
    download_media_not_in_structures: bool = True
    download_unfetched_media: bool = True
    download_full_versions_of_fetched_media: bool = True
    download_highest_quality_assets_from_structures: bool = True
    # What to do when an asset's file is missing on disk but its id appears in
    # downloaded_media_log.json (i.e. the archiver has acquired it before and
    # the user almost certainly deleted it on purpose):
    #   "reassemble_from_har_only" — don't touch the CDN; reassemble from HAR
    #       segments if available, otherwise skip.
    #   "skip"                     — don't acquire at all.
    #   "redownload"               — ignore the log entry; treat as fresh
    #       acquisition (full network fetch allowed, subject to the other flags).
    # The default keeps user deletions sticky across re-extraction runs.
    on_logged_missing: OnLoggedMissingVideo = "reassemble_from_har_only"
    # Restrict CDN acquisition (full-asset download and full-track download) to
    # videos belonging to a post the operator actually opened.
    #
    # Instagram preloads the head of every video in a profile timeline, so
    # scrolling a prolific account leaves dozens of videos with fetched_tracks —
    # and download_full_versions_of_fetched_media then pulls each one from the
    # CDN in full, even with download_unfetched_media=False. Archiving one reel
    # from deep in a timeline can cost hundreds of MB of collateral.
    #
    # When True, only videos found in an opened-post response (see
    # opened_post_structures) are eligible for a network fetch; everything else
    # falls back to reassembly from the bytes already in the HAR, so the
    # preloaded fragments are still preserved without re-downloading the asset.
    # Left False, mere presence in a fetched timeline merits a full download —
    # the historical behaviour.
    #
    # The restriction is skipped entirely (with a warning) for sessions that
    # contain no opened-post response at all — a Threads session, or one spent
    # only in the story viewer — because there "nothing was opened" is
    # indistinguishable from "this platform can't say", and failing closed would
    # silently drop media that has no HAR-segment fallback.
    download_full_assets_for_opened_posts_only: bool = False


def opened_post_video_ids(structures: Optional[list[StructureType]]) -> set[str]:
    """The canonical xpv_asset_ids of every video carried by an opened-post
    response, keyed exactly as acquire_videos keys its combined video map.

    Includes the ids derived from all quality variants (via
    _build_filename_xpv_map), not just video_versions[0], so an opened post is
    still recognised when the browser fetched a non-first rendition.
    """
    opened = opened_post_structures(structures or [])
    ids = {v.xpv_asset_id for v in extract_videos_from_structures(opened)}
    ids |= set(_build_filename_xpv_map(opened).values())
    return ids


def _requested_xpvs_from_urls(urls, struct_filename_to_xpv: dict[str, str]) -> set[str]:
    """Resolve an iterable of requested .mp4 URLs to the set of canonical
    xpv_asset_ids they refer to, keyed the same way the accumulation path keys
    videos (filename->xpv table first, then the URL's own efg/md5 id). Used to
    flag videos as requested-in-session even when no response body was captured."""
    requested: set[str] = set()
    for url in urls:
        if not isinstance(url, str) or '.mp4' not in url:
            continue
        fn = url.split('.mp4')[0].split('/')[-1]
        if fn:
            requested.add(struct_filename_to_xpv.get(fn, fn))
        xpv = extract_xpv_asset_id(url)
        if xpv:
            requested.add(xpv)
    return requested


def acquire_videos(
        har_path: Path,
        output_dir: Path = Path('../temp_video_segments'),
        structures: Optional[list[StructureType]] = None,
        config: VideoAcquisitionConfig = VideoAcquisitionConfig(),
        har_video_maps: Optional[list['Video']] = None,
        download_log: Optional['dl.DownloadLog'] = None,
        requested_mp4_urls: Optional[set[str]] = None,
) -> list[Video]:
    # unpack the config
    download_missing = config.download_missing
    download_media_not_in_structures = config.download_media_not_in_structures
    download_unfetched_media = config.download_unfetched_media
    download_full_versions_of_fetched_media = config.download_full_versions_of_fetched_media
    download_highest_quality_assets_from_structures = config.download_highest_quality_assets_from_structures
    on_logged_missing = config.on_logged_missing

    # None => no restriction in force. A set => only these ids may be fetched
    # from the CDN; every other video is limited to HAR-segment reassembly.
    opened_post_xpvs: Optional[set[str]] = None
    if config.download_full_assets_for_opened_posts_only:
        if opened_post_structures(structures or []):
            opened_post_xpvs = opened_post_video_ids(structures)
            print(f"[acquire] Opened-post restriction active: {len(opened_post_xpvs)} video id(s) "
                  f"eligible for CDN acquisition; all others limited to HAR-segment reassembly.")
        else:
            print("[acquire] download_full_assets_for_opened_posts_only is set, but this session "
                  "contains no opened-post response (no media-info / shortcode query / permalink "
                  "page load). Restriction NOT applied -- every video stays eligible.")

    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Drop manifest/par2 sidecars whose primary asset is gone (user deleted
    # files between runs). Keeps the eventual seal manifest clean.
    prune_orphan_sidecars(Path(output_dir))

    existing_videos = get_existing_videos(output_dir)

    har_videos = har_video_maps if har_video_maps is not None else extract_video_maps(har_path)
    structures_videos = extract_videos_from_structures(structures or [])

    combined_videos_dict: dict[str, Video] = {}

    for video in har_videos:
        if video.xpv_asset_id in combined_videos_dict:
            combined_videos_dict[video.xpv_asset_id].fetched_tracks = video.fetched_tracks
        else:
            combined_videos_dict[video.xpv_asset_id] = video

    # Final cascade step 2 for extract_video_maps: re-key any filename-fallback
    # HAR entries that can now be matched to a canonical xpv_asset_id.
    # Uses _build_filename_xpv_map (which covers ALL video_versions quality levels,
    # not just video_versions[0]) so the re-key succeeds even when the browser
    # fetched a non-first-quality variant.
    struct_filename_to_xpv = _build_filename_xpv_map(structures or [])
    for fn, real_xpv in list(struct_filename_to_xpv.items()):
        if fn in combined_videos_dict and fn != real_xpv:
            fn_video = combined_videos_dict.pop(fn)
            if real_xpv in combined_videos_dict:
                existing_tracks = combined_videos_dict[real_xpv].fetched_tracks
                if fn_video.fetched_tracks and existing_tracks is not None:
                    for track_name, track in fn_video.fetched_tracks.items():
                        if track_name not in existing_tracks:
                            existing_tracks[track_name] = track
            else:
                combined_videos_dict[real_xpv] = fn_video.model_copy(update={'xpv_asset_id': real_xpv})

    for video in structures_videos:
        if video.xpv_asset_id in combined_videos_dict:
            existing = combined_videos_dict[video.xpv_asset_id]
            existing.full_asset = video.full_asset
            # Carry the full-asset download candidates (and cover) from the
            # structure onto the HAR-derived entry so download_full_asset can
            # try every video_versions/DASH-BaseURL URL before reassembly.
            existing.full_asset_candidates = video.full_asset_candidates
            if video.cover_photo_url and not existing.cover_photo_url:
                existing.cover_photo_url = video.cover_photo_url
        else:
            combined_videos_dict[video.xpv_asset_id] = video

    combined_videos = list(combined_videos_dict.values())

    # Mark which videos were actually requested during the session — even when no
    # response body was captured. A Threads video the operator watched produces a
    # bytes=0- request in the HAR but no fetched_track (the media pipeline consumes
    # the body), so fetched_tracks alone would wrongly classify it as "unfetched"
    # and skip its CDN re-acquisition. The set of requested .mp4 URLs is normally
    # collected by the caller during its single HAR pass (requested_mp4_urls); only
    # when a caller didn't supply it do we fall back to a cheap URL-only scan here.
    if requested_mp4_urls is None:
        requested_mp4_urls = set()
        try:
            with open(har_path, 'rb') as f:
                for url in ijson.items(f, 'log.entries.item.request.url'):
                    if isinstance(url, str) and '.mp4' in url:
                        requested_mp4_urls.add(url)
        except Exception as e:
            print(f"[acquire] requested-asset scan failed (treating none as requested): {e}")
    requested_xpv = _requested_xpvs_from_urls(requested_mp4_urls, struct_filename_to_xpv)
    for video in combined_videos:
        if video.xpv_asset_id in requested_xpv:
            video.requested_in_session = True

    # attach existing local files to the videos
    for video in combined_videos:
        safe_xpv = _safe_id(video.xpv_asset_id)
        possible_stems = [
            f"xpv_{safe_xpv}",
            f"xpv_{safe_xpv}_full",
        ]
        for track_name in (video.fetched_tracks or {}):
            safe_track = _safe_id(track_name)
            possible_stems.append(f"track_{safe_xpv}_{safe_track}_har_segments")
            possible_stems.append(f"track_{safe_xpv}_{safe_track}_full_track")

        matching = [existing_videos[s] for s in possible_stems if s in existing_videos]
        if matching:
            print(f"Skipping video {video.xpv_asset_id} as it already exists in the output directory.")
            video.local_files = matching
            continue

    def _matched_source(result: AssetSaveResult, video: Video) -> dl.VideoSource:
        # Best-effort categorisation of which acquisition path produced the file.
        loc = result.location
        if loc is not None:
            name = loc.name
            if name.endswith('_full.mp4') and '_full_track' not in name:
                return "full_asset"
            if '_har_segments' in name:
                return "har_segments"
            if '_full_track' in name:
                return "har_full_track"
        # Fallback: infer from what's present on the video object.
        if video.full_asset:
            return "full_asset"
        return "har_segments"

    for video in combined_videos:
        # File already on disk → link normally and refresh the log entry.
        if video.local_files is not None and len(video.local_files) > 0:
            if download_log is not None:
                dl.upsert_video(
                    download_log,
                    video.xpv_asset_id,
                    video.local_files,
                    _matched_source(AssetSaveResult(location=video.local_files[0]), video),
                )
            continue

        # download_missing=False means "read-only pass, do not write anything
        # new to disk" — used by db_loaders stage C. Skip every acquisition
        # branch, including the reassembly fallback.
        if not download_missing:
            continue

        logged = (
            download_log is not None
            and video.xpv_asset_id in download_log.videos
        )

        # Not part of a post the operator opened -> no CDN traffic for this
        # asset. It can still be rebuilt from the bytes already in the HAR.
        cdn_restricted = (
            opened_post_xpvs is not None
            and video.xpv_asset_id not in opened_post_xpvs
        )

        # User previously curated this asset away (file missing + in log).
        # Apply the configured policy.
        if logged and on_logged_missing == "skip":
            print(f"[log] Video {video.xpv_asset_id} is in the download log but missing on disk -- skipping per on_logged_missing=skip.")
            continue
        if logged and on_logged_missing == "reassemble_from_har_only":
            if not video.fetched_tracks:
                print(f"[log] Video {video.xpv_asset_id} is in the log but missing and no HAR segments available -- skipping (no CDN fetch under reassemble_from_har_only).")
                continue
            print(f"[log] Video {video.xpv_asset_id} is in the log but missing -- reassembling from HAR segments only (no CDN fetch).")
            download_result = save_fetched_asset(
                video,
                output_dir,
                download_full_track=download_full_versions_of_fetched_media and not cdn_restricted,
            )
            if download_result.location is not None:
                video.local_files = [download_result.location]
                if download_log is not None:
                    dl.upsert_video(
                        download_log,
                        video.xpv_asset_id,
                        video.local_files,
                        _matched_source(download_result, video),
                    )
            continue

        # Fresh acquisition path: either id is not in the log at all, or the
        # caller asked for a forced redownload.
        download_result = AssetSaveResult(success=False)
        skip_video = (
            (not download_media_not_in_structures and not video.full_asset) or
            (not download_unfetched_media and not video.fetched_tracks
             and not video.requested_in_session)
        )
        if skip_video:
            continue
        if (
            (not download_result.success) and
            download_highest_quality_assets_from_structures and
            video.full_asset and
            not cdn_restricted
        ):
            download_result = download_full_asset(video, output_dir)
        if (
            (not download_result.success) and video.fetched_tracks
        ):
            download_result = save_fetched_asset(
                video,
                output_dir,
                download_full_track=download_full_versions_of_fetched_media and not cdn_restricted,
            )
        if download_result.location is not None:
            if video.local_files is None:
                video.local_files = []
            video.local_files.append(download_result.location)
            if download_log is not None:
                dl.upsert_video(
                    download_log,
                    video.xpv_asset_id,
                    video.local_files,
                    _matched_source(download_result, video),
                )

    stored_videos = []
    for video in combined_videos:
        if video.local_files is None or len(video.local_files) == 0:
            print(f"Video {video.xpv_asset_id} not downloaded.")
            continue
        stored_videos.append(video)
    return stored_videos


if __name__ == '__main__':
    # Provide the path to your .har file and desired output folder
    har_file = input("Input path to HAR file: ")  # Replace with your actual HAR file
    har_file = har_file.strip().strip('"').strip("'")
    har_file_path = Path(har_file)
    har_structures = structures_from_har(har_file_path)
    acquire_videos(
        har_file_path,
        output_dir=har_file_path.parent / "videos",
        structures=har_structures,
        config=VideoAcquisitionConfig(
            download_missing=True,
            download_media_not_in_structures=False,
            download_unfetched_media=False,
            download_full_versions_of_fetched_media=False,
            download_highest_quality_assets_from_structures=False
        )
    )
