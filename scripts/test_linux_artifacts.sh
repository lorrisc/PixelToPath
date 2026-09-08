#!/usr/bin/env bash
# test_linux_artifacts.sh — rejoue le « premier lancement utilisateur » sur des
# distros vierges : chaque conteneur part de l'image officielle SANS aucune
# dépendance de l'app préinstallée. Seuls xvfb + polices (pour conduire la
# fenêtre) et fuse3/fuse (pour tester le chemin « double-clic » — monté comme
# sur un bureau réel) sont ajoutés : aucun ne fait partie de l'app ni de ses
# dépendances.
#
# Ce que ça valide par image :
#   1. AppImage  : montage fuse + GUI vivant 20 s sous Xvfb, libcairo embarquée ;
#   2. CLI       : ptp --help (charge vtracer natif + i18n), conversion réel
#                  → SVG non vide (licence de test semée : is_pro() accepte une
#                  clé + validation < 7 j, core/licensing.py) ;
#   3. .run      : installation dans un PREFIX temporaire, CLI + GUI installées.
#
# Plancher garanti : glibc 2.34 (base de build Alma 9). Debian 11 (glibc 2.31,
# EOL 08/2026) est HORS matrice par défaut.
#
# Variables : IMAGES="…" pour restreindre (déf. almalinux:9 ubuntu:22.04
# ubuntu:24.04 debian:12).
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(grep -oP '(?<=^APP_VERSION = ")[^"]+' core/constants.py)
ARCH=$(uname -m)
APP="dist/PixelToPath-${VERSION}-${ARCH}.AppImage"
RUNF="dist/PixelToPath-${VERSION}-linux-${ARCH}.run"
PTPBIN="dist/ptp"
FIX="tests/fixtures/smoke.png"
LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT

for f in "$APP" "$RUNF" "$PTPBIN" "$FIX"; do
    [ -e "$f" ] || { echo "artefact manquant : $f (scripts/build_linux.sh d'abord)" >&2; exit 1; }
done

IMAGES="${IMAGES:-almalinux:9 ubuntu:22.04 ubuntu:24.04 debian:12}"
failed=""

for IMG in $IMAGES; do
    podman image exists "$IMG" || podman pull -q "$IMG" >/dev/null
    echo ""
    echo "══════════════ $IMG ══════════════"

    FUSE=""
    [ -e /dev/fuse ] && FUSE="--device /dev/fuse"

    # shellcheck disable=SC2086
    rc=0
    podman run --rm -i --security-opt label=disable $FUSE \
            -v "$PWD":/src:ro \
            -e APP="/src/$APP" -e RUNF="/src/$RUNF" \
            -e PTPBIN="/src/$PTPBIN" -e FIX="/src/$FIX" \
            "$IMG" /bin/bash -s >"$LOG" 2>&1 <<'CHECKS' || rc=$?
set -uo pipefail   # pas de -e : accumuler tous les échecs, code de sortie final
fail=0
step() { echo; echo "── $* ──"; }

# xvfb + polices : pour CONDUIRE la fenêtre uniquement. fuse : chemin
# « double-clic » (montage) — présent par défaut sur les bureaux réels.
NO_XVFB=""
ID="$(. /etc/os-release && echo "${ID:-unknown}")"
case "$ID" in
    ubuntu|debian)
        apt-get update -qq >/dev/null 2>&1 \
        && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
               xvfb xauth fonts-dejavu-core fuse3 >/dev/null 2>&1 \
        || NO_XVFB=1 ;;
    *)
        dnf -y -q install xorg-x11-server-Xvfb xorg-x11-fonts-misc fuse \
            >/dev/null 2>&1 || NO_XVFB=1 ;;
esac
[ -n "$NO_XVFB" ] && echo "(pas de Xvfb/fuse installables : GUI = liaison seule)"

# Licence de test : is_pro() accepte une clé + validation < 7 j. Format naïf
# (sans fuseau) comme `_now()` de core/licensing.py — un horodatage avec
# offset ferait planter la soustraction naive/aware.
mkdir -p ~/.config/PixelToPath
printf '{"pro": {"license_key": "ARTIFACT-TEST", "last_validated_at": "%s"}}\n' \
    "$(date +"%Y-%m-%dT%H:%M:%S")" > ~/.config/PixelToPath/config.json

link_probe() {  # doit échouer sur « no display » (Tk), JAMAIS sur la liaison
    local out rc
    set +e; out=$(timeout 15 "$1" 2>&1); rc=$?; set -e
    case "$out" in
        *"error while loading shared libraries"*|*"GLIBC_"*" not found"*)
            echo "✗ liaison ELF/glibc impossible :"
            printf '%s\n' "$out" | head -4; fail=1 ;;
        *) echo "✓ chargement ELF/glibc OK (rc=$rc attendu : pas d'affichage)" ;;
    esac
}

gui_smoke() {   # GUI vivant 20 s sous Xvfb = démarrage complet (Tk, CTK, vues)
    # GUI_SMOKESOFT=1 : l'échec n'incrémente pas fail (repli prévu juste après).
    if [ -n "$NO_XVFB" ]; then link_probe "$1"; return; fi
    local rc
    set +e
    timeout 20 xvfb-run -a -s "-screen 0 1280x900x24" "$@" >/tmp/gui.log 2>&1
    rc=$?
    set -e
    if [ "$rc" -eq 124 ]; then
        echo "✓ GUI démarré et vivant (arrêté après 20 s)"
    else
        echo "✗ GUI rc=$rc (fuse indisponible dans le conteneur rootless) :"
        tail -12 /tmp/gui.log
        [ -z "${GUI_SMOKESOFT:-}" ] && fail=1
        return 1
    fi
}

step "AppImage : montage fuse + GUI (mode « double-clic »)"
if ! GUI_SMOKESOFT=1 gui_smoke "$APP"; then
    echo "   → repli extraction (--appimage-extract-and-run)"
    gui_smoke "$APP" --appimage-extract-and-run
fi

step "AppImage : libcairo embarquée"
rm -rf squashfs-root
"$APP" --appimage-extract >/dev/null 2>&1 || true
if [ -e squashfs-root/usr/bin/_internal/libcairo.so.2 ]; then
    echo "✓ libcairo.so.2 embarquée (aucune dépend système pour l'aperçu)"
else
    echo "✗ libcairo absente de l'AppImage"; fail=1
fi
rm -rf squashfs-root

step "CLI : ptp --help (charge vtracer natif + i18n)"
if "$PTPBIN" --help >/tmp/ptp.log 2>&1; then
    echo "✓"
else
    echo "✗"; tail -6 /tmp/ptp.log; fail=1
fi

step "CLI : conversion moteur → SVG"
mkdir -p /tmp/out
if "$PTPBIN" convert "$FIX" -o /tmp/out >/tmp/conv.log 2>&1 \
        && [ -s "$(ls /tmp/out/*.svg 2>/dev/null | head -1)" ]; then
    echo "✓ SVG produit : $(ls /tmp/out/*.svg | head -1)"
else
    echo "✗ conversion :"; tail -8 /tmp/conv.log; fail=1
fi

step ".run : installation dans /tmp/ptp-inst"
if PIXELTOPATH_PREFIX=/tmp/ptp-inst sh "$RUNF" >/tmp/install.log 2>&1; then
    echo "✓ installée : $(ls /tmp/ptp-inst/bin | tr '\n' ' ')"
else
    echo "✗ :"; tail -8 /tmp/install.log; fail=1
fi

step ".run : CLI installée"
if /tmp/ptp-inst/bin/ptp --help >/dev/null 2>&1; then echo "✓"; else echo "✗"; fail=1; fi

step ".run : GUI installée"
gui_smoke /tmp/ptp-inst/lib/PixelToPath/PixelToPath || true

echo ""
if [ "$fail" -eq 0 ]; then
    echo "✅ $ID : tous les tests passent"
else
    echo "❌ $ID : $fail échec(s)"
fi
exit "$fail"
CHECKS
cat "$LOG"
if [ "$rc" -ne 0 ]; then
    failed="$failed $IMG"
fi
done

echo ""
if [ -z "$failed" ]; then
    echo "═══ ✅ Tous les artefacts passent sur : $IMAGES ═══"
else
    echo "═══ ❌ Échecs sur :$failed ═══"
    exit 1
fi
