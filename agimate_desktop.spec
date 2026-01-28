# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Agimate Desktop."""

import sys
from pathlib import Path

block_cipher = None

# Paths
ROOT = Path(SPECPATH)
PLUGINS_DIR = ROOT / 'plugins'

# Collect all plugin files as data
ASSETS_DIR = ROOT / 'assets'

datas = [
    # Plugins directory with configs
    (str(PLUGINS_DIR), 'plugins'),
]

# Add assets if exists
if ASSETS_DIR.exists():
    datas.append((str(ASSETS_DIR), 'assets'))

# Hidden imports for dynamic plugin loading
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'qasync',
    'aiohttp',
    'watchdog',
    'watchdog.observers',
    'watchdog.events',
    'centrifuge',
]

a = Analysis(
    ['main.py'],
    pathex=[str(ROOT)],
    binaries=[],
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

# Platform-specific settings
if sys.platform == 'darwin':
    # macOS: Create .app bundle
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='AgimateDesktop',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
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
        name='AgimateDesktop',
    )
    app = BUNDLE(
        coll,
        name='AgimateDesktop.app',
        icon=None,  # Add icon path here: 'assets/icon.icns'
        bundle_identifier='com.agimate.desktop',
        info_plist={
            'LSUIElement': True,  # Hide from Dock (menu bar app)
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '1.0.0',
        },
    )
else:
    # Windows/Linux: Single executable
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='AgimateDesktop',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,  # No console window
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,  # Add icon path here: 'assets/icon.ico' for Windows
    )
