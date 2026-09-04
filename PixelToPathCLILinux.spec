# PixelToPathCLILinux.spec
# CLI Pro (`ptp`) — onefile comme le build Linux du GUI, console VISIBLE.
# Prérequis : bootloader recompilé depuis les sources PyInstaller
# pip install vtracer Pillow

from PyInstaller.building.build_main import Analysis, PYZ, EXE
from PyInstaller.utils.hooks import collect_submodules
import sys, os

block_cipher = None

# La CLI n'importe jamais interface/ : core/ + moteur/ uniquement.
# Pas de cairosvg (rendu d'aperçu réservé au GUI).

a = Analysis(
    ['cli.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[
        ('moteur',  'moteur'),
        ('locales', 'locales'),
    ],
    hiddenimports=[
        'vtracer',
        *collect_submodules('PIL'),
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'customtkinter', 'tkinterdnd2',     # GUI uniquement
        'tkinter', 'tkinter.ttk',           # la CLI n'ouvre aucune fenêtre
        'cairosvg',                         # aperçu GUI uniquement
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
    name='ptp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,              # UPX déclenche les AV
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon='interface/assets/app_icon.ico',
)
