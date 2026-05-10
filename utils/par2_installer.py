# Detect or install par2cmdline-turbo and add it to PATH.
import json
import os
import platform
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

PAR2_RELEASES_API = "https://api.github.com/repos/animetosho/par2cmdline-turbo/releases/latest"
PAR2_LOCATION_FILE_REL = Path("utils") / "integrity" / "par2_location.txt"


def find_par2_executable_in_dir(par2_dir: Path) -> Optional[Path]:
    if not par2_dir.is_dir():
        return None
    exe_name = "par2.exe" if os.name == "nt" else "par2"
    for root, _dirs, files in os.walk(par2_dir):
        if exe_name in files:
            return Path(root) / exe_name
    return None


def _print_manual_install_hint() -> None:
    print(
        "PAR2 was not found and could not be auto-installed. Bitrot-recovery files\n"
        "will be skipped during archiving (chunk-level SHA-256 manifests and\n"
        "OpenTimestamps proofs are still generated — bitrot will be detectable but\n"
        "not repairable).\n"
        "\n"
        "To install par2cmdline-turbo:\n"
        "  1) Run:  winget install Animetosho.par2cmdline-turbo\n"
        "  2) Restart this shell so the new PATH entry takes effect.\n"
        "\n"
        "Alternatively, download a release from\n"
        "  https://github.com/animetosho/par2cmdline-turbo/releases\n"
        "and save the directory containing par2.exe to\n"
        f"  {PAR2_LOCATION_FILE_REL}"
    )


def _try_path() -> bool:
    check_cmd = "par2 --version >nul 2>&1" if os.name == "nt" else "par2 --version >/dev/null 2>&1"
    return os.system(check_cmd) == 0


def _try_local_install(par2_dir: Path) -> bool:
    par2_exe = find_par2_executable_in_dir(par2_dir)
    if par2_exe:
        os.environ["PATH"] = str(par2_exe.parent) + os.pathsep + os.environ.get("PATH", "")
        return True
    return False


def _windows_arch_tokens() -> tuple[str, ...]:
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return ("arm64",)
    if machine in ("amd64", "x86_64"):
        return ("x64", "amd64", "x86_64")
    if machine in ("x86", "i386", "i686"):
        return ("x86", "i386", "i686")
    return ()


def _pick_windows_asset(assets: list[dict]) -> Optional[dict]:
    arch_tokens = _windows_arch_tokens()
    win_zips = [a for a in assets if "win" in a["name"].lower() and a["name"].lower().endswith(".zip")]
    # Prefer assets matching this machine's arch, while avoiding arm64 on x64 hosts.
    for token in arch_tokens:
        for a in win_zips:
            name = a["name"].lower()
            if token in name and ("arm64" not in name or token == "arm64"):
                return a
    # Last resort: first windows zip that is not arm64 (avoid the wrong-arch binary).
    for a in win_zips:
        if "arm64" not in a["name"].lower():
            return a
    return win_zips[0] if win_zips else None


def _auto_download_windows(par2_dir: Path) -> bool:
    print("par2 not found, fetching latest release from GitHub...")
    req = urllib.request.Request(
        PAR2_RELEASES_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "InstagramArchiver"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        release = json.loads(resp.read().decode("utf-8"))

    candidate = _pick_windows_asset(release.get("assets", []))
    if not candidate:
        print("Could not find a Windows par2 release asset on the latest GitHub release.")
        return False

    url = candidate["browser_download_url"]
    print(f"Downloading {candidate['name']}...")
    par2_zip = Path(os.getcwd()) / "par2.zip"
    try:
        urllib.request.urlretrieve(url, par2_zip)
        with zipfile.ZipFile(par2_zip, "r") as zf:
            zf.extractall(par2_dir)
    finally:
        if par2_zip.exists():
            par2_zip.unlink()

    return _try_local_install(par2_dir)


def ensure_par2_installed() -> None:
    print("Ensuring PAR2 is installed...")
    if _try_path():
        print("par2 is already installed and accessible.")
        return

    par2_dir = Path(os.getcwd()) / "utils" / "par2"
    if _try_local_install(par2_dir):
        print("local installation of par2 found and added to PATH.")
        return

    if os.name != "nt":
        _print_manual_install_hint()
        return

    try:
        if _auto_download_windows(par2_dir):
            print("par2 downloaded and installed successfully.")
            return
    except Exception as e:
        print(f"Could not auto-install par2: {e}")

    _print_manual_install_hint()


if __name__ == "__main__":
    ensure_par2_installed()
