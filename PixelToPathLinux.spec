# PixelToPathLinux.spec
# Prérequis : bootloader recompilé depuis les sources PyInstaller
# pip install vtracer cairosvg customtkinter tkinterdnd2 Pillow numpy
# Sur Linux, cairosvg utilise libcairo du système (pas besoin de gtk-bin)

from PyInstaller.building.build_main import Analysis, PYZ, EXE
from PyInstaller.utils.hooks import collect_submodules
import sys, os

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[
        ('interface', 'interface'),
        ('moteur',    'moteur'),
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'vtracer',
        *collect_submodules('cairosvg'),
        *collect_submodules('customtkinter'),
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'pandas',
        'IPython', 'jupyter',
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
    name='PixelToPath',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,              # UPX déclenche les AV
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='interface/assets/app_icon.ico',
)
