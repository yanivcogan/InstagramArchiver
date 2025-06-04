# archive.spec
import subprocess
from PyInstaller.utils.hooks import collect_all

# Get current commit ID
try:
    commit_id = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode('utf-8').strip()
except:
    commit_id = "unknown"

# Write commit ID to a file that will be included in the bundle
with open('commit_id.txt', 'w') as f:
    f.write(commit_id)

block_cipher = None

datas = [('commit_id.txt', '.')]
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
    runtime_hooks=[],
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
    [],
    exclude_binaries=True,
    name='InstagramArchiver',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='InstagramArchiver',
)