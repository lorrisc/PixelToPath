# PixelToPathLinuxDir.spec
# Variante ONEDIR du build Linux GUI : layout canonique pour l'AppImage
# (scripts/build_appimage.sh) — démarrage immédiat, pas d'auto-extraction.
# Le onefile (PixelToPathLinux.spec) reste la cible « binaire nu ».

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.utils.hooks import collect_submodules
import sys, os

block_cipher = None

# Backend SNI de l'icône système (interface/tray_sni.py) : StatusNotifierItem
# natif sur le bus session — icône réelle sous Plasma/Wayland, pas de relais
# xembedsniproxy ni de demande de grabs d'entrée. Pur Python, aucun binaire.
SNI_IMPORTS = ['dbus_next', *collect_submodules('dbus_next')]

a = Analysis(
    ['app.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[
        ('interface', 'interface'),
        ('moteur',    'moteur'),
        ('locales',   'locales'),
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'vtracer',
        'potrace',                      # port pur Python de Potrace (moteur binaire)
        *collect_submodules('cairosvg'),
        *collect_submodules('customtkinter'),
        # Icône de barre système : pystray choisit son backend par imports
        # conditionnels (appindicator/ayatana/xorg) invisibles à l'analyse
        # statique — tout embarquer, plus python-xlib pour le backend xorg.
        *collect_submodules('pystray'),
        *collect_submodules('Xlib'),
        *SNI_IMPORTS,  # tray SNI natif (Wayland/KDE)
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

# libgcc_s : NE PAS embarquer. La copie de la base de build (Alma 9) exige
# GLIBC_2.35 — symboles rétroportés par EL9 dans sa glibc 2.34, absents des
# glibc ≥ 2.34 pures (Fedora 35-36…). Comme les wheels manylinux : celle du
# système cible (présente partout, toujours cohérente avec sa glibc).
a.binaries = [x for x in a.binaries if 'libgcc_s' not in x[0]]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir : les binaires partent dans le COLLECT
    name='PixelToPath',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX déclenche les AV
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
    upx_exclude=[],
    name='PixelToPath',
)
