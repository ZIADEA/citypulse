# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir — CityPulse Logistics. Lancer depuis la racine du dépôt : pyinstaller citypulse.spec"""
import sys
from pathlib import Path

from PyInstaller.building.datastruct import Tree

ROOT = Path(SPECPATH)

datas = []
if (ROOT / "settings.json").is_file():
    datas.append((str(ROOT / "settings.json"), "."))
for sub in ("data", "assets"):
    p = ROOT / sub
    if p.is_dir():
        datas += Tree(str(p), prefix=sub)
comp = ROOT / "app" / "ui" / "components"
if comp.is_dir():
    datas += Tree(str(comp), prefix="app/ui/components")

hiddenimports = [
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebChannel",
    "PyQt6.QtPrintSupport",
    "ortools",
    "keyring",
]
if sys.platform == "win32":
    hiddenimports.append("keyring.backends.Windows")

excludes = ["tkinter", "matplotlib.tests", "numpy.tests"]

block_cipher = None

version_info = None
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    version_info = VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=(1, 0, 0, 0),
            prodvers=(1, 0, 0, 0),
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("CompanyName", "CityPulse"),
                            StringStruct("FileDescription", "CityPulse Logistics"),
                            StringStruct("FileVersion", "1.0.0.0"),
                            StringStruct("InternalName", "citypulse"),
                            StringStruct("LegalCopyright", "Copyright (c) CityPulse"),
                            StringStruct("OriginalFilename", "citypulse.exe"),
                            StringStruct("ProductName", "CityPulse Logistics"),
                            StringStruct("ProductVersion", "1.0.0.0"),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )

icon_path = ROOT / "assets" / "icon.ico"
icon_arg = str(icon_path) if icon_path.is_file() else None

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
    name="citypulse",
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
    icon=icon_arg,
    version=version_info,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="citypulse",
)
