#!/usr/bin/env bash
# build_installer.sh — artefact Linux « un seul fichier » :
# installateur auto-extractible .run (format makeself) qui installe
# de manière PERMANENTE dans ~/.local :
#   ~/.local/lib/PixelToPath/   GUI (onedir : exe + _internal)
#   ~/.local/bin/PixelToPath    lanceur (lien)
#   ~/.local/bin/ptp            CLI Pro (lien)
#   ~/.local/share/applications + icônes  → menu des applications
#   ~/.local/bin/pixeltopath-uninstall    → désinstallation propre
# Aucun sudo, la config utilisateur (~/.config/PixelToPath) est préservée.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-env/bin/python}"

VERSION=$(grep -oP '(?<=^APP_VERSION = ")[^"]+' core/constants.py)
ARCH=$(uname -m)
OUT="dist/PixelToPath-${VERSION}-linux-${ARCH}.run"

echo "── PixelToPath ${VERSION} (${ARCH}) : builds ──"
"$PY" -m PyInstaller --noconfirm --clean PixelToPathLinuxDir.spec    # GUI onedir
"$PY" -m PyInstaller --noconfirm --clean PixelToPathCLILinux.spec    # CLI onefile

# Post-traitement « compatible tous » (libgcc_s système + cairo embarqué) ;
# à refaire ici : le --clean de PyInstaller régénère dist/PixelToPath de zéro.
bash scripts/bundle_compat.sh dist/PixelToPath/_internal

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/payload"
cp -a dist/PixelToPath "$STAGE/payload/PixelToPath"
cp dist/ptp "$STAGE/payload/ptp"
# Trois résolutions du même logo (dérivés de l'asset 180 px de la marque)
# : Kickoff/la barre des tâches choisissent la taille la plus adaptée.
cp interface/assets/app_icon.png     "$STAGE/payload/pixel-to-path.png"
cp interface/assets/app_icon_128.png "$STAGE/payload/pixel-to-path-128.png"
cp interface/assets/app_icon_256.png "$STAGE/payload/pixel-to-path-256.png"
tar -C "$STAGE/payload" -czf "$STAGE/payload.tar.gz" .

{
  printf '#!/bin/sh\n# PixelToPath %s — installateur permanent (GUI + CLI).\nPIXELTOPATH_VERSION="%s"\n' \
      "$VERSION" "$VERSION"
  cat <<'HEADER'
# Installateur auto-extractible : tout sous ~/.local, aucun root requis.
set -eu
PREFIX="${PIXELTOPATH_PREFIX:-$HOME/.local}"
LIB="$PREFIX/lib/PixelToPath"
BIN="$PREFIX/bin"
APP="$PREFIX/share/applications"
ICONS="$PREFIX/share/icons/hicolor/64x64/apps"

echo "PixelToPath $PIXELTOPATH_VERSION — installing to $PREFIX ..."

# ── Extraction du payload (à partir du marqueur) ──
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
SKIP=$(awk '/^__PAYLOAD_BELOW__$/ {print NR + 1; exit}' "$0")
tail -n "+$SKIP" "$0" | tar xzf - -C "$WORK"

# ── Binaires ──
mkdir -p "$LIB" "$BIN" "$APP" "$ICONS"
rm -rf "${LIB:?}"/*
cp -a "$WORK/PixelToPath/." "$LIB/"
cp "$WORK/ptp" "$LIB/ptp"
chmod +x "$LIB/PixelToPath" "$LIB/ptp"
ln -sf "$LIB/PixelToPath" "$BIN/PixelToPath"
ln -sf "$LIB/ptp" "$BIN/ptp"

# ── Intégration desktop ──
for size in 64x64 128x128 256x256; do
    mkdir -p "$PREFIX/share/icons/hicolor/$size/apps"
done
cp "$WORK/pixel-to-path.png"     "$ICONS/pixel-to-path.png"
cp "$WORK/pixel-to-path-128.png" "$PREFIX/share/icons/hicolor/128x128/apps/pixel-to-path.png"
cp "$WORK/pixel-to-path-256.png" "$PREFIX/share/icons/hicolor/256x256/apps/pixel-to-path.png"
cat > "$APP/pixel-to-path.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=PixelToPath
GenericName=Image to SVG converter
Comment=Turn pixel images into embroidery, laser and cutting-ready vector paths
Exec=$LIB/PixelToPath
Icon=pixel-to-path
Terminal=false
StartupNotify=true
Categories=Graphics;VectorGraphics;2DGraphics;
# WM_CLASS posé par App (className="PixelToPath") : rattache la tâche
# au .desktop → icône et nom réels dans la barre des tâches (Wayland inclus).
# Tcl force l'initiale majuscule : la partie classe de WM_CLASS donne
# "Pixeltopath" — StartupWMClass doit correspondre EXACTEMENT pour que la
# tâche soit rattachée au .desktop (icône + nom dans la barre).
StartupWMClass=Pixeltopath
DESKTOP

# ── Désinstallation (la config ~/.config/PixelToPath est conservée) ──
cat > "$BIN/pixeltopath-uninstall" <<UNINSTALL
#!/bin/sh
rm -rf "$LIB"
rm -f "$BIN/ptp" "$BIN/PixelToPath" "$BIN/pixeltopath-uninstall"
rm -f "$APP/pixel-to-path.desktop"
rm -f "$PREFIX/share/icons/hicolor/64x64/apps/pixel-to-path.png"
rm -f "$PREFIX/share/icons/hicolor/128x128/apps/pixel-to-path.png"
rm -f "$PREFIX/share/icons/hicolor/256x256/apps/pixel-to-path.png"
rm -f "${XDG_CACHE_HOME:-\$HOME/.cache}/icon-cache.kcache"
update-desktop-database "$APP" 2>/dev/null || true
kbuildsycoca6 2>/dev/null || kbuildsycoca5 2>/dev/null || true
echo "PixelToPath removed. Your settings were kept in:"
echo "  \$HOME/.config/PixelToPath  (delete it yourself if desired)"
UNINSTALL
chmod +x "$BIN/pixeltopath-uninstall"

# ── Bases de données desktop (best-effort) ──
# kbuildsycoca : KDE/Kickoff indexe .desktop + icônes dans son cache sycoca ;
# sans ce passage explicite le menu peut rester aveugle plusieurs minutes.
# icon-cache.kcache : raster cache de KIconLoader — s'il est périmé, le menu,
# la barre des tâches ET le tray SNI (lookup par nom) affichent des icônes
# génériques. Il se régénère seul : suppression sûre.
update-desktop-database "$APP" 2>/dev/null || true
gtk-update-icon-cache -q -f -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true
kbuildsycoca6 2>/dev/null || kbuildsycoca5 2>/dev/null || true
rm -f "${XDG_CACHE_HOME:-$HOME/.cache}/icon-cache.kcache" 2>/dev/null || true

# ── PATH : ~/.local/bin est normalement déjà dedans ──
case ":$PATH:" in
    *":$BIN:"*) ;;
    *) echo ""
       echo "  NOTE: add $BIN to your PATH to use 'ptp' and 'PixelToPath'"
       echo "  from a terminal (usually done in ~/.bashrc or ~/.profile)."
       echo "" ;;
esac

echo "Installed:"
echo "  $BIN/PixelToPath   (GUI - also in your applications menu)"
echo "  $BIN/ptp           (CLI - Pro)"
echo ""
echo "Get started:"
echo "  PixelToPath                launch the app"
echo "  ptp license activate KEY   activate your Pro license"
echo "  ptp convert img.png -o svg/"
echo ""
echo "Uninstall anytime with: pixeltopath-uninstall"
HEADER
  # exit 0 : le shell n'atteint jamais la ligne marqueur (sinon « commande
  # introuvable » + exit 127 à la toute fin de l'installation).
  printf 'exit 0\n__PAYLOAD_BELOW__\n'
  cat "$STAGE/payload.tar.gz"
} > "$OUT"
chmod +x "$OUT"

mkdir -p dist
ls -lh "$OUT"
