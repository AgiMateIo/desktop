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

# Add assets if exists (brand SVGs live here and are read at runtime)
if ASSETS_DIR.exists():
    datas.append((str(ASSETS_DIR), 'assets'))

# Packaging icons, generated from assets/brand/connector-tile.svg by
# `python build.py icons`. Absent on a tree that has not run it yet, so the
# build stays possible without them.
ICNS = ASSETS_DIR / 'icon.icns'
ICO = ASSETS_DIR / 'icon.ico'

# Hidden imports for dynamic plugin loading
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    # The brand marks are SVG, rendered at runtime for the tray
    'PySide6.QtSvg',
    'qasync',
    'aiohttp',
    'watchdog',
    'watchdog.observers',
    'watchdog.events',
    'centrifuge',
    'psutil',
    # macOS window listing (dynamically imported by window_list plugin)
    'Quartz',
    # system_info collectors (dynamically loaded via plugin system)
    'plugins.tools.system_info.collectors',
    'plugins.tools.system_info.collectors.os_info',
    'plugins.tools.system_info.collectors.cpu_info',
    'plugins.tools.system_info.collectors.memory_info',
    'plugins.tools.system_info.collectors.disk_info',
    'plugins.tools.system_info.collectors.network_info',
    'plugins.tools.system_info.collectors.uptime_info',
    'plugins.tools.system_info.collectors.screen_info',
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
        icon=str(ICNS) if ICNS.exists() else None,
        bundle_identifier='com.agimate.desktop',
        info_plist={
            'LSUIElement': True,  # Hide from Dock (menu bar app)
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '0.2.0',
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
        icon=str(ICO) if ICO.exists() else None,
    )
