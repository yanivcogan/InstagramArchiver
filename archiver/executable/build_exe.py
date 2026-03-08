import subprocess
import sys
from pathlib import Path

# This script lives at archiver/executable/build_exe.py
# Project root is two levels up
root_dir = Path(__file__).resolve().parent.parent.parent
spec_file = root_dir / "archiver" / "executable" / "archive.spec"
work_path = root_dir / "archiver" / "executable" / "build"
dist_path = root_dir / "archiver" / "executable" / "dist"

subprocess.run(
    [
        sys.executable, "-m", "PyInstaller",
        "--workpath", str(work_path),
        "--distpath", str(dist_path),
        str(spec_file),
    ],
    cwd=root_dir,
    check=True,
)
