import os
import subprocess
import sys
from PyInstaller.utils.hooks import collect_all

# Get current commit ID
try:
    commit_id = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode('utf-8').strip()
except:
    commit_id = "unknown"

# Write commit ID to a file that will be included in the bundle
with open('commit_id.txt', 'w') as f:
    f.write(commit_id)

# Install Playwright Firefox to a local directory
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
try:
    subprocess.run([sys.executable, "-m", "playwright", "install", "firefox"], check=True)
except Exception as e:
    print(f"Failed to install Playwright browsers: {e}")

# Get Playwright browsers path
import tempfile
with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
    f.write(b"""
import os
import sys
from playwright.sync_api import sync_playwright
print(os.path.dirname(sync_playwright()._playwright._playwright_cr._playwright_path))
""")
browsers_path_script = f.name

try:
    playwright_path = subprocess.check_output([sys.executable, browsers_path_script]).decode('utf-8').strip()
    os.unlink(browsers_path_script)
except Exception as e:
    print(f"Failed to detect Playwright path: {e}")
    playwright_path = os.path.join(os.path.expanduser("~"), ".cache", "ms-playwright")
    if not os.path.exists(playwright_path):
        playwright_path = os.path.join(os.path.expanduser("~"), ".playwright")

# Package browser files
browser_datas = []
if os.path.exists(playwright_path):
    # Add firefox directory with all its contents
    firefox_path = os.path.join(playwright_path, "firefox-*")
    browser_datas.append((firefox_path, "firefox"))

block_cipher = None

datas = [('commit_id.txt', '.')]
datas.extend(browser_datas)

# Include necessary data files from each package
binaries = []
hiddenimports = ['cv2', 'pyautogui', 'numpy', 'playwright', 'threading']

a = Analysis(
    ['archive.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hook-exception.py'],  # Add our exception hook
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,           # Include binaries for onefile mode
    a.zipfiles,           # Include zipfiles for onefile mode
    a.datas,              # Include data files for onefile mode
    [],
    name='InstagramArchiver',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,   # Recommended for onefile mode
    console=True,         # Keep this as True to show the console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)