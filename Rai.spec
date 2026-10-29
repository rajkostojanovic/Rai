# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


hiddenimports = collect_submodules("PySide6.QtMultimedia") + collect_submodules("soundcard")
root = Path(globals().get("SPECPATH", Path.cwd())).resolve()


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        (str(root / "logo.png"), "."),
        (str(root / "logo.ico"), "."),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Rai",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(root / "logo.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Rai",
)
