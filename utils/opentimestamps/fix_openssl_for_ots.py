"""
fix_openssl_for_ots.py

Creates ssl.dll in the venv's Scripts directory as a copy of libssl-3-x64.dll.
Run this after every `uv sync` if ots stamps start failing with a ctypes SSL error.

Why: python-bitcoinlib (a dependency of opentimestamps-client) calls
ctypes.util.find_library('ssl') which looks for 'ssl.dll' on Windows.
The actual OpenSSL DLL is named 'libssl-3-x64.dll', so find_library returns None.
The venv's Scripts directory is on PATH when the venv is activated, so placing
ssl.dll there makes it discoverable.

Usage:
    uv run python utils/opentimestamps/fix_openssl_for_ots.py
"""
import shutil
import sys
from pathlib import Path

site_packages = Path(sys.prefix) / "Lib" / "site-packages"
scripts = Path(sys.prefix) / "Scripts"
# python-bitcoinlib loads 'ssl' but actually needs libcrypto (BN_add, EC_*, ECDSA_*, etc.)
src = site_packages / "libcrypto-3-x64.dll"
dst = scripts / "ssl.dll"

if not src.exists():
    print(f"ERROR: {src} not found — cannot create ssl.dll alias.")
    sys.exit(1)

shutil.copy2(src, dst)
print(f"Created {dst}")
print("ots should now work when the venv is activated.")
