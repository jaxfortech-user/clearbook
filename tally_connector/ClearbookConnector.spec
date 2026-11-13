# -*- mode: python ; coding: utf-8 -*-
# ClearbookConnector.spec
# PyInstaller spec for Clearbook Tally Connector
# Build: pyinstaller ClearbookConnector.spec

import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Collect websockets and httpx fully (they use dynamic imports internally)
ws_datas, ws_binaries, ws_hiddenimports = collect_all('websockets')
httpx_datas, httpx_binaries, httpx_hiddenimports = collect_all('httpx')
httpcore_datas, httpcore_binaries, httpcore_hiddenimports = collect_all('httpcore')

a = Analysis(
    ['connector.py'],
    pathex=['.'],
    binaries=ws_binaries + httpx_binaries + httpcore_binaries,
    datas=ws_datas + httpx_datas + httpcore_datas,
    hiddenimports=(
        ws_hiddenimports
        + httpx_hiddenimports
        + httpcore_hiddenimports
        + [
            'tkinter',
            'tkinter.messagebox',
            'tkinter.ttk',
            'win32api',
            'win32con',
            'win32event',
            'win32service',
            'win32serviceutil',
            'servicemanager',
            'pywintypes',
            'asyncio',
            'asyncio.base_events',
            'asyncio.events',
            'asyncio.futures',
            'asyncio.tasks',
            'asyncio.windows_events',
            'config',
            'ssl',
            '_ssl',
        ]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'PIL', 'scipy'],
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
    name='ClearbookConnector',
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
)
