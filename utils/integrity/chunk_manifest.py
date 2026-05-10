"""
Chunked SHA-256 manifest builder + verifier.

Each protected asset gets a sidecar `<asset>.manifest.json` containing the
whole-file SHA-256, per-chunk SHA-256s, and a binary Merkle root over the chunk
digests. The manifest itself is OpenTimestamped, so every chunk hash is
indirectly anchored by the manifest's OTS proof. After bitrot, chunks whose
hashes still match the manifest are provably unchanged since archive time.
"""

import datetime
import hashlib
import json
from pathlib import Path
from typing import Optional

DEFAULT_CHUNK_SIZE = 1 << 20  # 1 MiB
ALGORITHM = "sha256"
MANIFEST_VERSION = 1


def _merkle_root(chunk_digests: list[bytes]) -> bytes:
    if not chunk_digests:
        return hashlib.sha256(b"").digest()
    layer = list(chunk_digests)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [
            hashlib.sha256(layer[i] + layer[i + 1]).digest()
            for i in range(0, len(layer), 2)
        ]
    return layer[0]


def build_manifest(
    path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    par2: Optional[dict] = None,
) -> dict:
    path = Path(path)
    chunk_hex: list[str] = []
    chunk_digests: list[bytes] = []
    whole = hashlib.sha256()
    size = 0

    with open(path, "rb") as f:
        while True:
            buf = f.read(chunk_size)
            if not buf:
                break
            size += len(buf)
            digest = hashlib.sha256(buf).digest()
            chunk_digests.append(digest)
            chunk_hex.append(digest.hex())
            whole.update(buf)

    manifest: dict = {
        "version": MANIFEST_VERSION,
        "filename": path.name,
        "size": size,
        "algorithm": ALGORITHM,
        "chunk_size": chunk_size,
        "chunk_count": len(chunk_hex),
        "whole_file_sha256": whole.hexdigest(),
        "merkle_root": _merkle_root(chunk_digests).hex(),
        "chunks": chunk_hex,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    if par2 is not None:
        manifest["par2"] = par2
    return manifest


def serialize_manifest(manifest: dict) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_manifest(manifest: dict, out_path: Path) -> str:
    """Write the manifest deterministically and return its SHA-256 hex."""
    payload = serialize_manifest(manifest)
    out_path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def read_manifest(path: Path) -> dict:
    return json.loads(Path(path).read_bytes().decode("utf-8"))


def verify_against_manifest(path: Path, manifest: dict) -> "ChunkVerifyReport":
    chunk_size = manifest["chunk_size"]
    expected_chunks = manifest["chunks"]
    expected_whole = manifest["whole_file_sha256"]

    actual_chunks: list[str] = []
    whole = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            buf = f.read(chunk_size)
            if not buf:
                break
            actual_chunks.append(hashlib.sha256(buf).hexdigest())
            whole.update(buf)

    bad_indices = [
        i
        for i, (a, e) in enumerate(zip(actual_chunks, expected_chunks))
        if a != e
    ]
    length_mismatch = len(actual_chunks) != len(expected_chunks)
    whole_ok = whole.hexdigest() == expected_whole

    return ChunkVerifyReport(
        whole_file_ok=whole_ok and not length_mismatch,
        chunk_count=len(expected_chunks),
        bad_chunk_indices=bad_indices,
        length_mismatch=length_mismatch,
    )


from pydantic import BaseModel  # noqa: E402  (kept here so the dataclass-ish report sits next to its consumers)


class ChunkVerifyReport(BaseModel):
    whole_file_ok: bool
    chunk_count: int
    bad_chunk_indices: list[int]
    length_mismatch: bool
