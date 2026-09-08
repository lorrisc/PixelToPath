#!/usr/bin/env bash
# build_linux.sh — artefacts Linux « compatibles tous » : build en conteneur.
#
# Pourquoi : un binaire compilé sur la machine hôte (Fedora 44, glibc 2.43)
# refuse de démarrer sur les distros un peu anciennes (« version GLIBC_2.xx
# not found »). On compile donc DANS un conteneur AlmaLinux 9 (glibc 2.34),
# ce qui couvre Debian 12+, Ubuntu 22.04+, Mint 21+, RHEL/Rocky/Alma 9+,
# Fedora 35+, Arch, openSUSE Leap 15.4+ — et produit les MÊMES artefacts
# qu'avant, via les scripts existants inchangés :
#   dist/PixelToPath-<v>-linux-x86_64.run   (installateur, build_installer.sh)
#   dist/PixelToPath-<v>-x86_64.AppImage    (build_appimage.sh)
#
# Prérequis : podman. Le build ne touche à rien sur l'hôte : les volumes
# pointent sur le dépôt et des caches (~/.cache/ptp-build, ~/.cache/ptp-pip).
#
# Options :
#   IMAGE=<nom>          image conteneur à utiliser (déf. pixeltopath-linux-builder)
#   CONTAINERFILE=<path> déf. scripts/Containerfile.linux-build
#   GLIBC_MAX=<x.y>      plancher audit (déf. 2.34) : build échoue si un ELF
#                        exige une glibc plus récente
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="${IMAGE:-pixeltopath-linux-builder}"
CONTAINERFILE="${CONTAINERFILE:-scripts/Containerfile.linux-build}"
GLIBC_MAX="${GLIBC_MAX:-2.34}"

command -v podman >/dev/null || { echo "podman introuvable (sudo dnf install podman)" >&2; exit 1; }

podman build -t "$IMAGE" -f "$CONTAINERFILE" .

mkdir -p dist "$HOME/.cache/ptp-build" "$HOME/.cache/ptp-pip"

# --userns=keep-id : le processus tourne avec l'uid hôte → tout ce qui est
# écrit dans /src (dist/, build/) appartient à l'utilisateur, pas à root.
# label=disable : SELinux Fedora bloque sinon la lecture des montages bind
# (classique « Permission denied » en conteneur de build — sans risque ici).
podman run --rm -i --userns=keep-id --security-opt label=disable \
    -e HOME=/home/build \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -e GLIBC_MAX="$GLIBC_MAX" \
    -v "$PWD":/src -w /src \
    -v "$HOME/.cache/ptp-build":/home/build/.cache/ptp-build \
    -v "$HOME/.cache/ptp-pip":/home/build/.cache/pip \
    "$IMAGE" /bin/bash -s <<'INNER'
set -euo pipefail
cd /src

echo "── venv python3.11 + dépendances ──"
python3.11 -m venv /tmp/venv
PY=/tmp/venv/bin/python
"$PY" -m pip install -q --upgrade pip
# pyinstaller épinglé ici : requirements.txt sert aussi à l'env hôte, la
# version de build de référence est unique (6.22.2).
grep -vE '^pyinstaller==' requirements.txt > /tmp/requirements.txt
echo 'pyinstaller==6.22.2' >> /tmp/requirements.txt
"$PY" -m pip install -q -r /tmp/requirements.txt
"$PY" -c 'import sys, tkinter; print("── interpréteur :", sys.version.split()[0], "· Tk", tkinter.TkVersion, "──")'
echo "── glibc de build : $(ldd --version | head -1 | awk '{print $NF}') ──"

# Artefacts .run (GUI onedir + CLI onefile + installateur) et AppImage.
# Les deux scripts appellent scripts/bundle_cairo.sh après CHAQUE build
# PyInstaller (cairo est dlopen : invisible de PyInstaller).
PY="$PY" scripts/build_installer.sh
PY="$PY" scripts/build_appimage.sh

echo "── Audit glibc ≤ ${GLIBC_MAX} (dist/PixelToPath, dist/ptp) ──"
fail=0
while IFS= read -r -d '' f; do
    for v in $(objdump -T "$f" 2>/dev/null | grep -oE 'GLIBC_[0-9]+\.[0-9]+' | sort -u); do
        v="${v#GLIBC_}"
        smallest=$(printf '%s\n%s\n' "$GLIBC_MAX" "$v" | sort -V | head -1)
        if [ "$smallest" = "$GLIBC_MAX" ] && [ "$v" != "$GLIBC_MAX" ]; then
            echo "  ✗ $f exige GLIBC_$v (> ${GLIBC_MAX})"
            fail=1
        fi
    done
done < <(find dist/PixelToPath dist/ptp -type f -print0 | while IFS= read -r -d '' f; do
    file -b "$f" | grep -q ELF && printf '%s\0' "$f"
    true
done)

# L'archive onefile (dist/ptp) échappe à objdump : audit de son contenu.
if "$PY" -m PyInstaller.utils.cliutils.archive_viewer -l dist/ptp 2>/dev/null | grep -q 'libgcc_s'; then
    echo "  ✗ libgcc_s encore embarquée dans l'archive onefile"
    fail=1
fi
if [ "$fail" -eq 0 ]; then
    echo "  ✓ tous les ELF tiennent dans glibc ≤ ${GLIBC_MAX}"
fi
exit "$fail"
INNER

echo ""
echo "── Artefacts Linux (compatibles Debian 12+ · Ubuntu 22.04+ · Fedora 35+ · EL9+) ──"
ls -lh dist/*.AppImage dist/*.run 2>/dev/null
