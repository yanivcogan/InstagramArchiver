"""
timestamper.py

Windows-friendly helper utilities to create and verify OpenTimestamps (OTS)
proofs using the `ots` CLI (opentimestamps-client). Contains two main public
functions:

- timestamp_file(filepath: Path, ots_file: Optional[Path] = None) -> Path
- verify_timestamp(data_file: Path, ots_file: Optional[Path] = None) -> None

This module also provides helper functions that ensure:
- the `ots` CLI is on PATH or a saved user location is used; and
- OpenSSL DLLs are findable by ctypes when the `ots` subprocess runs
  (the error you reported arises because the Python process invoked by `ots`
  imports a bitcoin library that tries to load an OpenSSL DLL via ctypes).

Important notes:
- Designed for Windows (PowerShell) usage.
- This module does not attempt to directly import `otsclient` itself — the module
  invokes the `ots` command-line program as a subprocess so the CLI's wrapper
  script will handle the Python-side imports in its own process. We ensure the
  child process can find OpenSSL DLLs by adding a user-specified directory to PATH.
- The module uses two small files in the project root to persist user-provided
  locations:
    - open_timestamps_location.txt  (where `ots.exe` lives)
    - open_ssl_location.txt         (where OpenSSL DLLs live)

How this addresses your specific error:
- The traceback you pasted shows `ctypes.util.find_library('ssl')` returned None
  and a subsequent LoadLibrary(None) caused a TypeError. The fix is to ensure
  the directory with the OpenSSL DLLs (e.g. libssl-*.dll / libcrypto-*.dll /
  ssleay32.dll / libeay32.dll) is on PATH so ctypes can find them when the
  child `ots` process imports the bitcoin/OpenSSL-based modules.

Testing instructions are provided at the bottom of this file (PowerShell examples).
"""

import os
import shutil
import subprocess
import ctypes.util
from pathlib import Path
from typing import Optional

# If your project has a root anchor you usually import, adjust this path.
# For compatibility, we try to locate a root file named root_anchor.py as in your
# repository. If not found, fall back to current working directory.
try:
    # root_anchor.py in your repo defines ROOT_DIR; prefer that when available.
    from root_anchor import ROOT_DIR  # type: ignore
except Exception:
    ROOT_DIR = Path.cwd()

# Files used to persist user-provided locations
OTS_LOCATION_FILE = Path(ROOT_DIR) / "open_timestamps_location.txt"
OPENSSL_LOCATION_FILE = Path(ROOT_DIR) / "open_ssl_location.txt"


def ensure_ots_on_path() -> None:
    """
    Ensure the `ots` CLI executable is available on PATH. Windows systems will
    often have a wrapper `ots.exe` in the Python Scripts directory.

    Behavior:
    - If `ots` is on PATH, return immediately.
    - If a saved path exists in `open_timestamps_location.txt` and contains
      'ots.exe', add that directory to PATH and return.
    - Otherwise, prompt the user for the directory that contains `ots.exe`,
      save it in the file, and add it to PATH. If not provided or invalid,
      raise FileNotFoundError.

    Example:
      python -m pip install opentimestamps-client
      Then provide something like:
      C:/Users/<you>/AppData/Local/Programs/Python/Python313/Scripts
    """
    if shutil.which("ots"):
        return

    ots_dir = None
    if OTS_LOCATION_FILE.exists():
        try:
            stored = OTS_LOCATION_FILE.read_text(encoding="utf-8").strip()
            if stored:
                candidate = Path(stored)
                if (candidate / "ots.exe").exists() or shutil.which(str(candidate / "ots.exe")):
                    ots_dir = candidate
        except Exception:
            pass

    if ots_dir is None:
        print("OpenTimestamps CLI (ots) not found on PATH.")
        print("If you haven't installed it, run:")
        print("  python -m pip install opentimestamps-client")
        user_dir = input(
            "Enter the directory containing ots.exe (or press Enter to abort): "
        ).strip().strip('"').strip("'")
        if user_dir:
            ots_dir = Path(user_dir)
            # store for future runs
            try:
                OTS_LOCATION_FILE.write_text(str(ots_dir), encoding="utf-8")
            except Exception:
                # Don't fail just because we couldn't persist the path.
                pass

    if ots_dir is None or not (ots_dir / "ots.exe").exists():
        raise FileNotFoundError(
            "Could not locate ots.exe. Add it to PATH or provide a valid directory."
        )

    # Prepend to PATH so subprocesses inherit it
    os.environ["PATH"] = str(ots_dir) + os.pathsep + os.environ.get("PATH", "")


def _find_openssl_dlls_in_dir(candidate_dir: Path):
    """
    Helper that checks a directory for likely OpenSSL DLL filenames.
    Returns a list of matching files (possibly empty).
    """
    dll_patterns = [
        "libssl*.dll",  # e.g., libssl-3.dll, libssl-1_1-x64.dll
        "libcrypto*.dll",
        "libeay32.dll",
        "ssleay32.dll",
        "libssl-*.dll",
        "*ssl*.dll",
        "*crypto*.dll",
    ]
    matches = []
    for pat in dll_patterns:
        matches.extend(candidate_dir.glob(pat))
    # Filter to files only, return as list of Path
    return [p for p in matches if p.is_file()]


def ensure_openssl_on_path() -> None:
    """
    Ensure a directory containing OpenSSL DLLs is on PATH for child processes.

    Rationale:
    - The OTS CLI's bundled Python code imports libraries that call
      `ctypes.cdll.LoadLibrary(ctypes.util.find_library('ssl') ...)`.
    - On some Windows setups ctypes.util.find_library returns None unless the
      OpenSSL DLL directory is discoverable; placing the directory on PATH
      helps the system find the DLLs.

    Behavior:
    - If ctypes.util.find_library('ssl') already returns a non-None value, do nothing.
    - Otherwise, look at a saved path in `open_ssl_location.txt` for candidate DLLs.
    - If that fails, prompt the user to enter the directory that contains the
      OpenSSL DLLs (where files like libssl-*.dll or libcrypto-*.dll live).
    - Save the user-provided path to `open_ssl_location.txt` for future runs.
    - If we still can't find any DLLs, raise FileNotFoundError (to allow the
      caller to show a helpful message).
    """
    # Quick check: if ctypes can already find the library, nothing to do.
    if ctypes.util.find_library("ssl") is not None:
        return

    candidate_dir = None
    # Try persisted location
    if OPENSSL_LOCATION_FILE.exists():
        try:
            stored = OPENSSL_LOCATION_FILE.read_text(encoding="utf-8").strip()
            if stored:
                cand = Path(stored)
                if cand.exists() and cand.is_dir():
                    if _find_openssl_dlls_in_dir(cand):
                        candidate_dir = cand
        except Exception:
            pass

    # If not found, ask the user
    if candidate_dir is None:
        print("OpenSSL DLLs not found by ctypes on this system.")
        print("This can cause OTS (opentimestamps) to fail with a TypeError while loading SSL.")
        print("If you have OpenSSL installed or bundled DLLs (libssl*.dll, libcrypto*.dll),")
        print("enter the directory path that contains these DLLs (e.g. C:/OpenSSL-Win64/bin or a Python/conda DLLs folder).")
        user_dir = input(
            "Enter the directory containing OpenSSL DLLs (or press Enter to abort): "
        ).strip().strip('"').strip("'")
        if user_dir:
            cand = Path(user_dir)
            if cand.exists() and cand.is_dir():
                if _find_openssl_dlls_in_dir(cand):
                    candidate_dir = cand
                    try:
                        OPENSSL_LOCATION_FILE.write_text(str(candidate_dir), encoding="utf-8")
                    except Exception:
                        pass
                else:
                    print(
                        "No obvious OpenSSL DLLs were found in that directory. "
                        "You may still add it to PATH manually if you know it's correct."
                    )

    # If we found a candidate directory, prepend it to PATH so subprocess inherits it.
    if candidate_dir:
        os.environ["PATH"] = str(candidate_dir) + os.pathsep + os.environ.get("PATH", "")
        # After adding to PATH, re-check ctypes.util.find_library for best effort
        if ctypes.util.find_library("ssl") is None:
            # On some Windows setups, find_library may still return None, but adding
            # to PATH can still allow LoadLibrary by exact dll filename. We'll accept
            # that and hope child process can load the DLL. We warn the user though.
            print(
                "Warning: ctypes.util.find_library('ssl') still returned None after adding the directory to PATH.\n"
                "Child processes may still succeed loading the DLL if it's on PATH. If failures continue,\n"
                "ensure you have a compatible OpenSSL build for your Python/OS and that the DLL filenames exist."
            )
        return

    # Nothing found; raise so callers can surface a helpful error
    raise FileNotFoundError(
        "Could not locate OpenSSL DLLs. Install OpenSSL for Windows or provide the directory "
        "that contains libssl*.dll and libcrypto*.dll and save it to "
        f"{OPENSSL_LOCATION_FILE}."
    )


def hash_file(filepath: Path) -> bytes:
    """
    Utility: returns the SHA-256 digest of a file as bytes.
    (Provided for completeness; OpenTimestamps uses the file data itself.)
    """
    import hashlib

    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).digest()


def timestamp_file(filepath: Path, ots_file: Optional[Path] = None) -> Path:
    """
    Create an OpenTimestamps (.ots) proof for `filepath`.

    - By default, the proof is created as `<filepath>.ots` in the same directory.
    - If `ots_file` is provided, the created .ots will be moved to that path.

    The function ensures the `ots` CLI is available and tries to make OpenSSL
    DLLs discoverable to the child process (to avoid the TypeError you posted).

    Returns:
      Path to the saved .ots file.

    Raises:
      - FileNotFoundError if `ots` CLI or OpenSSL DLLs cannot be located.
      - subprocess.CalledProcessError if the `ots` command fails for any reason;
        the error output is attached to the exception message.
    """
    ensure_ots_on_path()
    # Ensure OpenSSL on PATH before spawning the child process that imports modules
    ensure_openssl_on_path()

    filepath = Path(filepath).resolve()
    if not filepath.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")

    # Default proof filename: add .ots to the existing filename
    default_ots = filepath.with_suffix(filepath.suffix + ".ots")
    target_ots = Path(ots_file).resolve() if ots_file else default_ots

    cmd = ["ots", "stamp", str(filepath)]

    try:
        # Run the OTS CLI. Let CalledProcessError propagate with captured output.
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=os.environ.copy())
    except subprocess.CalledProcessError as exc:
        # Add context to the error message to help debug the OpenSSL/ctypes issue.
        msg_lines = [
            f"`ots stamp` failed with exit code {exc.returncode}.",
            "stdout:",
            (exc.stdout or "").strip(),
            "stderr:",
            (exc.stderr or "").strip(),
            "",
            "Common causes:",
            "- The `ots` CLI may not be installed or on PATH (see ensure_ots_on_path()).",
            "- The child Python process that runs `ots` may fail to load OpenSSL DLLs. If you saw",
            "  a traceback mentioning ctypes.util.find_library('ssl') or a TypeError LoadLibrary(None),",
            "  ensure you have a compatible OpenSSL installation and run ensure_openssl_on_path().",
            "",
            "To troubleshoot:",
            f" - Run: ots --version  (in a PowerShell window) to confirm the CLI runs.",
            f" - If you have an open_ssl_location.txt in the project root, verify it points to a directory with libssl*.dll and libcrypto*.dll.",
        ]
        raise RuntimeError("\n".join(msg_lines)) from exc

    # On success, the CLI created `<file>.ots`. Move it if the user requested a different path.
    if target_ots != default_ots:
        if not default_ots.exists():
            raise FileNotFoundError(f"Expected proof not found after stamping: {default_ots}")
        target_ots.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(default_ots), str(target_ots))

    return target_ots


def verify_timestamp(data_file: Path, ots_file: Optional[Path] = None) -> None:
    """
    Verify an OpenTimestamps proof.

    Usage patterns:
    - If `ots_file` is None: runs `ots verify <data_file>` expecting `<data_file>.ots` next to it.
    - If `ots_file` is provided: runs `ots verify <ots_file>`.

    The function ensures `ots` CLI and OpenSSL DLLs are available before running.

    The function prints the verification output. It raises a RuntimeError with
    helpful hints if the `ots` command fails.
    """
    ensure_ots_on_path()
    ensure_openssl_on_path()

    data_file = Path(data_file).resolve()
    if not data_file.exists():
        raise FileNotFoundError(f"Data file not found: {data_file}")

    default_ots = data_file.with_suffix(data_file.suffix + ".ots")

    if ots_file is None:
        cmd = ["ots", "verify", str(data_file)]
    else:
        ots_file = Path(ots_file).resolve()
        if not ots_file.exists():
            raise FileNotFoundError(f"OTS proof file not found: {ots_file}")
        cmd = ["ots", "verify", str(ots_file)]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=os.environ.copy())
    except subprocess.CalledProcessError as exc:
        msg_lines = [
            f"`ots verify` failed with exit code {exc.returncode}.",
            "stdout:",
            (exc.stdout or "").strip(),
            "stderr:",
            (exc.stderr or "").strip(),
            "",
            "Possible causes: proof file mismatch, network/calendar issues, or OpenSSL DLL load problems.",
            "You can re-run the same command in PowerShell to see interactive output:",
            "  ots verify <path>",
        ]
        raise RuntimeError("\n".join(msg_lines)) from exc

    # If we reach here, verification succeeded
    print("✅ OpenTimestamps verification output:")
    print(result.stdout.strip())


# Minimal interactive test function (not used by other code).
# The user specifically asked NOT to wire these into other code; this helper is
# just to allow manual testing from the command line.
def interactive_test_ui() -> None:
    mode = input("Timestamp a file (t) or verify (v)? ").strip().lower()
    if mode == "t":
        path = Path(input("Path to file to timestamp: ").strip().strip('"').strip("'"))
        out = timestamp_file(path)
        print(f"Created proof: {out}")
    elif mode == "v":
        data = Path(input("Path to data file: ").strip().strip('"').strip("'"))
        otsf = input("Path to .ots file (press Enter to use <data>.ots): ").strip().strip('"').strip("'")
        if otsf:
            verify_timestamp(data, Path(otsf))
        else:
            verify_timestamp(data)
    else:
        print("Unknown option. Use 't' or 'v'.")


# If run directly, allow an interactive test. This is optional.
if __name__ == "__main__":
    interactive_test_ui()


# -------------------------
# PowerShell test instructions (copy/paste in PowerShell)
# -------------------------
#
# 1) Install the OTS CLI into your venv or globally:
#    python -m pip install opentimestamps-client
#
# 2) Ensure your Python Scripts dir (containing ots.exe) is on PATH or run this
#    module and provide the path when prompted. Example Python Scripts path:
#    C:/Users/<you>/AppData/Local/Programs/Python/Python313/Scripts
#
# 3) If you hit the TypeError about ctypes LoadLibrary(None) (the issue you reported),
#    install or locate OpenSSL DLLs and provide their directory when prompted.
#    Common options:
#    - Install the Win64 OpenSSL binaries (from a trustworthy provider) and point to its bin dir.
#    - If using Conda, point to: C:/Users/<you>/miniconda3/Library/bin
#    - If using a Python distribution that bundles OpenSSL DLLs, point to that DLL directory.
#
# 4) Quick PowerShell try (after saving the file):
#    # Run Python REPL and try stamping a small file
#    python -c "from utils.timestamper import timestamp_file; from pathlib import Path; print(timestamp_file(Path('C:/path/to/somefile.txt')))"
#
# 5) Or run interactively:
#    python utils/timestamper.py
#
# If `ots` still fails in the spawned process, run `ots --version` in a separate
# PowerShell window to confirm the CLI is runnable. If `ots --version` crashes
# with the same ctypes/ssl error, that confirms the child process cannot find
# OpenSSL; supply the OpenSSL DLL directory as described above and re-run the
# tests.
#
# End of file