# PixelToPath.spec

from PyInstaller.building.build_main import COLLECT
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.building.build_main import Analysis, PYZ, EXE
import sys
import os

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[
        ('interface', 'interface'),
        ('moteur', 'moteur'),
        ('bin/gtk-bin', 'bin/gtk-bin'),
        ('bin/potrace-bin', 'bin/potrace-bin'),
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        *collect_submodules('cairosvg'),
    ],
    hookspath=[],
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
    exclude_binaries=True,  # Important pour onedir
    name='PixelToPath',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='interface/assets/app_icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='PixelToPath'
)
