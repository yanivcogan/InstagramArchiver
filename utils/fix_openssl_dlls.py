r"""
fix_openssl_dlls.py

Persistent helper to make OpenSSL DLLs discoverable for ctypes on Windows venvs.

Usage (recommended):
  1) Activate the project's venv.
  2) From project root run:
       python ./utils/fix_openssl_dlls.py
     This will:
       - locate libcrypto (preferred) or libssl in the venv site-packages,
       - copy one of those DLLs into the venv Scripts folder under several legacy names
         (ssl.35.dll, ssl.dll, libeay32.dll, ssleay32.dll),
       - optionally write open_ssl_location.txt to the project root containing the DLL directory
         (if the --persist flag is passed).
  3) Test with:
       python -c "import ctypes.util; print(ctypes.util.find_library('ssl'))"
       ots --version

Notes:
 - This script only copies existing DLLs (it does not download anything).
 - Copies are reversible (you can delete the created files).
 - It is intended to be run locally (per-developer). Do NOT commit the venv DLLs to repo.
"""

from pathlib import Path
import shutil
import sys
import sysconfig
import site
import argparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # repository root where utils/ lives
OPENSSL_LOCATION_FILE = PROJECT_ROOT / "open_ssl_location.txt"

def find_site_packages():
    # 1) prefer sysconfig purelib (works for venvs and conda)
    try:
        paths = sysconfig.get_paths()
        purelib = paths.get("purelib")
        if purelib:
            p = Path(purelib)
            if p.exists():
                return p
    except Exception:
        pass

    # 2) fallback to site.getsitepackages()
    try:
        sps = site.getsitepackages()
        for p in sps:
            ppath = Path(p)
            if ppath.exists():
                # prefer one under sys.prefix
                try:
                    if Path(sys.prefix).resolve() in ppath.resolve().parents or str(ppath.resolve()).startswith(str(Path(sys.prefix).resolve())):
                        return ppath
                except Exception:
                    return ppath
        for p in sps:
            ppath = Path(p)
            if ppath.exists():
                return ppath
    except Exception:
        pass

    # 3) typical venv path
    candidate = Path(sys.prefix) / "Lib" / "site-packages"
    if candidate.exists():
        return candidate

    # 4) usersite
    try:
        usp = site.getusersitepackages()
        if usp and Path(usp).exists():
            return Path(usp)
    except Exception:
        pass

    raise RuntimeError("Could not locate site-packages directory for this Python environment.")

def find_openssl_dlls(site_packages: Path):
    patterns = ["libcrypto*.dll", "libssl*.dll", "*ssl*.dll", "*crypto*.dll"]
    found = []
    for pat in patterns:
        found.extend(site_packages.glob(pat))
    return [p for p in found if p.is_file()]

def choose_preferred(src_files):
    # Prefer libcrypto over libssl
    src_crypto = None
    src_ssl = None
    for p in src_files:
        ln = p.name.lower()
        if ln.startswith("libcrypto") and src_crypto is None:
            src_crypto = p
        elif ln.startswith("libssl") and src_ssl is None:
            src_ssl = p
    return src_crypto or src_ssl or (src_files[0] if src_files else None)

def write_open_ssl_location(path: Path):
    try:
        OPENSSL_LOCATION_FILE.write_text(str(path), encoding="utf-8")
        print(f"Wrote OpenSSL DLL directory to {OPENSSL_LOCATION_FILE}")
    except Exception as e:
        print("Warning: could not persist open_ssl_location.txt:", e)

def copy_to_scripts(src: Path, scripts_dir: Path, target_names=None):
    if target_names is None:
        target_names = ["ssl.35.dll", "ssl.dll", "libeay32.dll", "ssleay32.dll"]
    created = []
    for name in target_names:
        dst = scripts_dir / name
        try:
            shutil.copyfile(src, dst)
            created.append(dst)
            print(f"Copied {src.name} -> {dst}")
        except Exception as e:
            print(f"Failed to copy {src} -> {dst}: {e}")
    return created

def copy_to_site_packages(src: Path, site_packages: Path, target_names=None):
    if target_names is None:
        target_names = ["ssl.35.dll", "ssl.dll", "libeay32.dll", "ssleay32.dll"]
    created = []
    for name in target_names:
        dst = site_packages / name
        try:
            shutil.copyfile(src, dst)
            created.append(dst)
            print(f"Copied {src.name} -> {dst}")
        except Exception as e:
            print(f"Failed to copy {src} -> {dst}: {e}")
    return created

def main(argv=None):
    parser = argparse.ArgumentParser(description="Make OpenSSL DLLs discoverable for ctypes on Windows venvs")
    parser.add_argument("--no-scripts", action="store_true", help="Don't copy DLLs to the venv Scripts directory (only site-packages)")
    parser.add_argument("--no-site", action="store_true", help="Don't copy DLLs to site-packages (only scripts)")
    parser.add_argument("--persist", action="store_true", help="Write open_ssl_location.txt to project root with the DLL directory")
    parser.add_argument("--dry-run", action="store_true", help="Do not copy, just show what would be done")
    args = parser.parse_args(argv)

    try:
        site_packages = find_site_packages()
    except RuntimeError as e:
        print("Error locating site-packages:", e)
        sys.exit(1)

    print("Detected site-packages:", site_packages)

    candidates = find_openssl_dlls(site_packages)
    if not candidates:
        print("No OpenSSL DLL candidates found in site-packages.")
        print("If you have OpenSSL installed elsewhere, you can pass that directory via open_ssl_location.txt or set PATH.")
        sys.exit(1)

    print("Found candidate DLLs:")
    for c in candidates:
        print("  ", c.name)

    preferred = choose_preferred(candidates)
    if not preferred:
        print("No suitable DLL found to copy.")
        sys.exit(1)

    print("Preferred source DLL:", preferred.name)

    scripts_dir = Path(sys.prefix) / "Scripts"
    print("Detected Scripts dir:", scripts_dir)

    if args.dry_run:
        print("Dry run: would copy to:")
        if not args.no_site:
            print("  site-packages:", site_packages)
        if not args.no_scripts:
            print("  scripts:", scripts_dir)
        if args.persist:
            print("  persist open_ssl_location.txt ->", OPENSSL_LOCATION_FILE)
        return

    # Copy to site-packages unless disabled
    if not args.no_site:
        copy_to_site_packages(preferred, site_packages)

    # Copy to scripts unless disabled
    if not args.no_scripts:
        if not scripts_dir.exists():
            print("Scripts dir does not exist:", scripts_dir)
        else:
            copy_to_scripts(preferred, scripts_dir)

    # Persist dll directory if requested (or always write it, you can change behavior)
    if args.persist:
        write_open_ssl_location(site_packages)

    print("Finished. You can now test:")
    print("  python -c \"import ctypes.util; print(ctypes.util.find_library('ssl'))\"")
    print("  ots --version")

if __name__ == "__main__":
    main()