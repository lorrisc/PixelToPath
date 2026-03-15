# PixelToPathWindows.spec
# Prérequis : bootloader recompilé depuis les sources PyInstaller
# pip install vtracer cairosvg customtkinter tkinterdnd2 Pillow numpy

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import sys, os

block_cipher = None

# vtracer expose une extension native (.pyd) — PyInstaller la détecte
# automatiquement via collect_submodules. cairosvg nécessite les DLLs GTK
# qui doivent être dans bin/gtk-bin/ (inchangé).

a = Analysis(
    ['app.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[
        ('interface',   'interface'),
        ('moteur',      'moteur'),
        # GTK toujours nécessaire pour cairosvg sur Windows
        ('bin/gtk-bin', 'bin/gtk-bin'),
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'vtracer',                          # extension Rust/pyo3
        *collect_submodules('cairosvg'),
        *collect_submodules('customtkinter'),
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'pandas',    # exclure les libs inutiles
        'IPython', 'jupyter',               # réduit la taille et la surface AV
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
    [],
    exclude_binaries=True,      # onedir : moins suspect qu'onefile
    name='PixelToPath',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                  # UPX déclenche les AV — toujours False
    console=False,
    icon='interface/assets/app_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='PixelToPath',
)
