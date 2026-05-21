"""
Thin subprocess wrapper around the zpaq CLI (`zpaq`).

zpaq is a journaling archiver tuned for cold-storage compression ratio. It
includes fragment-level deduplication as a side effect of the journaling
format, but provides no error-correction coding -- pair it with PAR2 (see
utils/integrity/par2.py) when durability matters.

The CLI is located via PATH first, then a project-local fallback file
(utils/compression/zpaq_location.txt) following the same pattern as
utils/integrity/par2.py.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

try:
    from root_anchor import ROOT_DIR
except Exception:
    ROOT_DIR = Path.cwd()

ZPAQ_LOCATION_FILE = Path(ROOT_DIR) / "utils" / "compression" / "zpaq_location.txt"

DEFAULT_LEVEL = 5
DEFAULT_THREADS = 1


class ZpaqNotFoundError(RuntimeError):
    pass


def _exe_name() -> str:
    return "zpaq.exe" if os.name == "nt" else "zpaq"


def find_zpaq_executable() -> Optional[Path]:
    found = shutil.which("zpaq")
    if found:
        return Path(found)
    if ZPAQ_LOCATION_FILE.exists():
        try:
            stored = ZPAQ_LOCATION_FILE.read_text(encoding="utf-8").strip()
            if stored:
                candidate = Path(stored)
                if candidate.is_file():
                    return candidate
                exe_in_dir = candidate / _exe_name()
                if exe_in_dir.is_file():
                    return exe_in_dir
        except Exception:
            pass
    local_dir = Path(ROOT_DIR) / "utils" / "compression" / "zpaq"
    if local_dir.is_dir():
        exe_name = _exe_name()
        for root, _dirs, files in os.walk(local_dir):
            if exe_name in files:
                return Path(root) / exe_name
    scripts_dir = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
    candidate = scripts_dir / _exe_name()
    if candidate.exists():
        return candidate
    return None


def ensure_zpaq_on_path() -> Path:
    exe = find_zpaq_executable()
    if exe is None:
        raise ZpaqNotFoundError(
            "Could not locate the `zpaq` executable. Install zpaq "
            "(http://mattmahoney.net/dc/zpaq.html) and put `zpaq.exe` on PATH, "
            "drop it into utils/compression/zpaq/, or save the directory "
            f"containing it to {ZPAQ_LOCATION_FILE}."
        )
    zpaq_dir = exe.parent
    if str(zpaq_dir) not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = str(zpaq_dir) + os.pathsep + os.environ.get("PATH", "")
    print("zpac found")
    return exe


def compress(
    input_path: Path,
    output_path: Path,
    level: int = DEFAULT_LEVEL,
    threads: int = DEFAULT_THREADS,
) -> Path:
    """
    Compress `input_path` into a new zpaq archive at `output_path`.

    zpaq is a journaling archiver: `zpaq a` appends a new version to any
    existing archive at the target path. To produce a clean single-version
    archive we delete `output_path` first if it exists.
    """
    exe = ensure_zpaq_on_path()
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Cannot compress missing file: {input_path}")
    if output_path.exists():
        output_path.unlink()

    cmd = [
        str(exe),
        "a",
        str(output_path),
        str(input_path),
        f"-m{int(level)}",
        f"-t{int(threads)}",
    ]
    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=str(output_path.parent),
    )
    return output_path


def decompress(zpaq_file: Path, output_dir: Path) -> Path:
    """
    Extract a zpaq archive into `output_dir`. Returns `output_dir`.
    """
    exe = ensure_zpaq_on_path()
    zpaq_file = Path(zpaq_file).resolve()
    output_dir = Path(output_dir).resolve()
    if not zpaq_file.exists():
        raise FileNotFoundError(f"Cannot decompress missing file: {zpaq_file}")
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(exe),
        "x",
        str(zpaq_file),
        "-to",
        str(output_dir),
    ]
    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=str(output_dir),
    )
    return output_dir


if __name__ == "__main__":
    ensure_zpaq_on_path()