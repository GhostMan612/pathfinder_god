# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

import sys
from pathlib import Path

SPEC_DIR = Path.cwd()
REPO_ROOT = SPEC_DIR.parents[2]
HUB_DIR = REPO_ROOT / "hub"
VENV_PYTHON = Path(r"C:\venv-hub\venv\Scripts\python.exe")

block_cipher = None

# Prepare datas list (filter None)
datas_list = []
chat_hist = SPEC_DIR / "chat_history.json"
if chat_hist.exists():
    datas_list.append((str(chat_hist), "."))
sounds_dir = SPEC_DIR / "sounds"
if sounds_dir.exists():
    datas_list.append((str(sounds_dir), "sounds"))

a = Analysis(
    ['main.py'],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'requests',
        'websockets',
        'websockets.sync.client',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'json',
        'threading',
        're',
        'random',
        'os',
        'sys',
        'pathlib',
        'services',
        'hub_api',
        'sfx',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL',
        'jupyter', 'notebook', 'IPython', 'pytest', 'setuptools',
        'wheel', 'pip', 'flask', 'django', 'fastapi', 'uvicorn',
        'sqlalchemy', 'alembic', 'psycopg2', 'pymongo', 'redis',
        'httpx', 'ollama', 'pydantic', 'pydantic_core',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PathfinderGodCommandCenter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',
)