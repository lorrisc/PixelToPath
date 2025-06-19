# PixelToPath-onefile.spec
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
        ('bin/potrace-1.16.linux-x86_64/potrace', 'bin/potrace-1.16.linux-x86_64/'),
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        *collect_submodules('cairosvg'),
        *collect_submodules('customtkinter'),
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PixelToPath',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,    
    console=False,
    icon='interface/assets/app_icon.ico',
)   