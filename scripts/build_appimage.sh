#!/usr/bin/env bash
# build_appimage.sh — artefact Linux standard pour la distribution :
# build PyInstaller ONEDIR (PixelToPathLinuxDir.spec) → AppDir → AppImage.
#
# Sortie : dist/PixelToPath-<version>-x86_64.AppImage
# Outil  : appimagetool (AppImage officielle, mise en cache dans
#          ~/.cache/ptp-build — aucun paquet système requis).
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-env/bin/python}"
TOOLCACHE="${HOME}/.cache/ptp-build"
APPIMAGETOOL="${TOOLCACHE}/appimagetool-x86_64.AppImage"

VERSION=$(grep -oP '(?<=^APP_VERSION = ")[^"]+' core/constants.py)
ARCH=$(uname -m)
echo "── PixelToPath ${VERSION} (${ARCH}) ──"

# 1. appimagetool (cache local, jamais dans le dépôt).
if [ ! -x "$APPIMAGETOOL" ]; then
    echo "── Téléchargement d'appimagetool ──"
    mkdir -p "$TOOLCACHE"
    curl -sL -o "$APPIMAGETOOL" \
        https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$APPIMAGETOOL"
fi

# 2. Build onedir.
echo "── Build onedir ──"
"$PY" -m PyInstaller --noconfirm --clean PixelToPathLinuxDir.spec

# 2bis. Post-traitement « compatible tous » : libgcc_s système + cairo
# embarqué (voir scripts/bundle_compat.sh).
bash scripts/bundle_compat.sh dist/PixelToPath/_internal

# 3. Assemblage de l'AppDir (layout usr/bin conventionnel).
# NB : l'arbre onedir complet vit dans dist/ (exe + _internal/) —
# build/<spec>/ ne contient que les intermédiaires PyInstaller.
APPDIR="build/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/icons/hicolor/64x64/apps" \
         "$APPDIR/usr/share/icons/hicolor/128x128/apps" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "dist/PixelToPath/." "$APPDIR/usr/bin/"
# Trois résolutions du même logo (dérivés de l'asset 180 px de la marque).
cp interface/assets/app_icon.png \
   "$APPDIR/usr/share/icons/hicolor/64x64/apps/pixel-to-path.png"
cp interface/assets/app_icon_128.png \
   "$APPDIR/usr/share/icons/hicolor/128x128/apps/pixel-to-path.png"
cp interface/assets/app_icon_256.png \
   "$APPDIR/usr/share/icons/hicolor/256x256/apps/pixel-to-path.png"
cp interface/assets/app_icon_128.png "$APPDIR/pixel-to-path.png"
ln -sf pixel-to-path.png "$APPDIR/.DirIcon"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
# AppImage : point d'entrée — l'exe PyInstaller trouve _internal/ à côté.
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/PixelToPath" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/pixel-to-path.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=PixelToPath
GenericName=Image to SVG converter
Comment=Turn pixel images into embroidery, laser and cutting-ready vector paths
Exec=AppRun %F
Icon=pixel-to-path
Terminal=false
StartupNotify=true
Categories=Graphics;VectorGraphics;2DGraphics;
StartupWMClass=Pixeltopath
X-AppImage-Version=${VERSION}
EOF

# 4. Empaquetage.
# --runtime-file : runtime type2 récent (type2-runtime) — libfuse y est lié
# STATIQUEMENT (binaire musl) : l'AppImage n'exige plus libfuse2 sur la
# machine cible (absente des distros 2024+, ex. Ubuntu 24.04). Seul /dev/fuse
# du noyau est requis, sinon `--appimage-extract-and-run`.
RUNTIME="${TOOLCACHE}/runtime-${ARCH}"
if [ ! -s "$RUNTIME" ]; then
    echo "── Téléchargement du runtime AppImage (fuse statique) ──"
    curl -sfL -o "$RUNTIME" \
        "https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-${ARCH}"
fi

OUT="dist/PixelToPath-${VERSION}-${ARCH}.AppImage"
mkdir -p dist
echo "── AppImage → ${OUT} ──"
if ! APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" --runtime-file "$RUNTIME" "$APPDIR" "$OUT"; then
    echo "── (Nouvel essai sans FUSE : mode extract-and-run) ──"
    APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" --runtime-file "$RUNTIME" "$APPDIR" "$OUT"
fi
ls -lh "$OUT"
