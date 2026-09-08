#!/usr/bin/env bash
# build_windows.sh — artefacts Windows construits DEPUIS Linux, via Wine.
#
# PyInstaller ne cross-compile pas : on fait tourner un Python Windows
# officiel (3.11, Tk 8.6 — combo éprouvé customtkinter/tkinterdnd2) dans un
# préfixe Wine DÉDIÉ (~/.wineptp, la config Wine personnelle n'est pas touchée).
#
# Sorties :
#   dist/Setup_PixelToPath-<v>.exe   installateur (Inno Setup, InstallPixelToPath.iss)
#   dist/PixelToPath-<v>-win64.zip   portable GUI + CLI (zip de secours)
#   build/win-stage/{PixelToPath,ptp}/  arbres onedir bruts
#
# Prérequis : sudo dnf install wine   (une seule fois)
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(grep -oP '(?<=^APP_VERSION = ")[^"]+' core/constants.py)
PYVER=3.11.9
PREFIX="${WINEPREFIX:-$HOME/.wineptp}"
CACHE="$HOME/.cache/ptp-build"
PYWIN='C:\Python311\python.exe'
ISCC='C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
STAGE="build/win-stage"

command -v wine >/dev/null || { echo "wine introuvable : sudo dnf install wine" >&2; exit 1; }
[ -e bin/gtk-bin/libcairo-2.dll ] || { echo "bin/gtk-bin/ absent (requis par PixelToPathWindows.spec)" >&2; exit 1; }
mkdir -p dist "$CACHE"

export WINEPREFIX="$PREFIX" WINEARCH=win64
# pas de Mono/Gecko (inutiles), pas de trace debug
export WINEDLLOVERRIDES="mscoree,mshtml=" WINEDEBUG=-all

# ── 1. Préfixe + Python Windows ──
if [ ! -x "$PREFIX/drive_c/Python311/python.exe" ]; then
    echo "── Python $PYVER amd64 (installation silencieuse sous Wine) ──"
    ISO="$CACHE/python-$PYVER-amd64.exe"
    [ -s "$ISO" ] || curl -sfL -o "$ISO" \
        "https://www.python.org/ftp/python/$PYVER/python-$PYVER-amd64.exe"
    wineboot -u >/dev/null 2>&1 || true
    wine "$ISO" /quiet InstallAllUsers=1 TargetDir='C:\Python311' \
        Include_tcltk=1 Include_pip=1 Include_test=0 AssociateFiles=0 Shortcuts=0
    wine "$PYWIN" -c "import sys, tkinter; print('Python', sys.version.split()[0], '· Tk', tkinter.TkVersion)"
fi

# ── 2. Dépendances ──
# requirements.txt tel quel : les paquets « Linux only » (python-xlib,
# dbus-next) sont purs Python et s'installent sans effet sous Windows ; les
# specs Windows n'en importent aucun. pyinstaller épinglé en argument.
echo "── pip (Windows) ──"
wine "$PYWIN" -m pip install -q -r requirements.txt 'pyinstaller==6.22.2'

# ── 3. Builds PyInstaller (distpath séparé : ne touche pas au dist Linux) ──
echo "── PyInstaller Windows : GUI + CLI ──"
wine "$PYWIN" -m PyInstaller --noconfirm --clean \
    --distpath "$STAGE" --workpath build/win \
    PixelToPathWindows.spec
wine "$PYWIN" -m PyInstaller --noconfirm --clean \
    --distpath "$STAGE" --workpath build/win \
    PixelToPathCLIWindows.spec
test -x "$STAGE/PixelToPath/PixelToPath.exe" && test -x "$STAGE/ptp/ptp.exe"

# ── 4. Installateur Inno Setup ──
if [ ! -x "$PREFIX/drive_c/Program Files (x86)/Inno Setup 6/ISCC.exe" ]; then
    echo "── Inno Setup 6 (installation silencieuse sous Wine) ──"
    ISETUP="$CACHE/innosetup-6.7.3.exe"
    [ -s "$ISETUP" ] || curl -sfL -o "$ISETUP" \
        "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe"
    wine "$ISETUP" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
fi

echo "── Installateur (ISCC) ──"
mkdir -p "$STAGE"
# Version injectée dans une copie du .iss : une seule source de vérité
# (core/constants.py) ; nom de sortie versionné.
sed -e "s/^AppVersion=.*/AppVersion=${VERSION}/" \
    -e "s/^OutputBaseFilename=.*/OutputBaseFilename=PixelToPath-${VERSION}-setup-win64/" \
    InstallPixelToPath.iss > "$STAGE/InstallPixelToPath.iss"
(cd "$STAGE" && wine "$ISCC" "InstallPixelToPath.iss")
test -e "$STAGE/output/PixelToPath-${VERSION}-setup-win64.exe"
cp "$STAGE/output/PixelToPath-${VERSION}-setup-win64.exe" dist/

# ── 5. Zip portable ──
echo "── Zip portable ──"
( cd "$STAGE" && zip -q -r "../../dist/PixelToPath-${VERSION}-win64.zip" PixelToPath ptp )

# ── 6. Vérifications sous Wine ──
echo "── Vérifications ──"
APPDIR="$PREFIX/drive_c/users/$(id -un)/AppData/Roaming/PixelToPath"
mkdir -p "$APPDIR"
# Format naïf (sans offset) comme _now() de core/licensing.py.
printf '{"pro": {"license_key": "BUILD-TEST", "last_validated_at": "%s"}}\n' \
    "$(date +"%Y-%m-%dT%H:%M:%S")" > "$APPDIR/config.json"

if wine "$STAGE/ptp/ptp.exe" --help >/tmp/ptp-win.log 2>&1; then
    echo "✓ ptp.exe --help"
else
    echo "✗ ptp.exe --help :"; tail -8 /tmp/ptp-win.log; exit 1
fi
mkdir -p /tmp/ptp-win-out
if wine "$STAGE/ptp/ptp.exe" convert tests/fixtures/smoke.png -o 'Z:\tmp\ptp-win-out' \
        >/tmp/conv-win.log 2>&1 && ls /tmp/ptp-win-out/*.svg >/dev/null 2>&1; then
    echo "✓ ptp.exe convert → $(ls /tmp/ptp-win-out/*.svg | head -1)"
else
    echo "✗ conversion :"; tail -8 /tmp/conv-win.log; exit 1
fi

if [ -n "${DISPLAY:-}" ]; then
    echo "── Smoke GUI (affiché via Xwayland, tué après 20 s) ──"
    set +e
    timeout 20 wine explorer /desktop=ptpgui,1280x900 "$STAGE/PixelToPath/PixelToPath.exe" >/tmp/gui-win.log 2>&1
    rc=$?
    set -e
    [ "$rc" -eq 124 ] && echo "✓ GUI vivant (arrêté après 20 s)" || { echo "✗ GUI rc=$rc :"; tail -10 /tmp/gui-win.log; exit 1; }
else
    echo "(pas de DISPLAY : smoke GUI sauté)"
fi

echo ""
echo "── Artefacts Windows ──"
ls -lh "dist/PixelToPath-${VERSION}-setup-win64.exe" "dist/PixelToPath-${VERSION}-win64.zip"
