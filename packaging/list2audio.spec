# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: single-file Windows executable with GUI (no console)."""

import sys

block_cipher = None

a = Analysis(
    ["../src/list2audio/gui/app.py"],
    pathex=["../src"],
    binaries=[],
    datas=[],
    hiddenimports=[
        "yt_dlp",
        "customtkinter",
        # yt-dlp loads extractors dynamically
        "yt_dlp.extractor",
        "yt_dlp.downloader",
        "yt_dlp.postprocessor",
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="list2audio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI app: no black terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # add packaging/icon.ico when we have one
)
