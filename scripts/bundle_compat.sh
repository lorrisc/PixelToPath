#!/usr/bin/env bash
# bundle_compat.sh — post-traitement « compatible tous » du onedir PyInstaller.
# Appelé après CHAQUE build PyInstaller (le --clean repart de zéro).
#
# 1. Retire libgcc_s.so.1 : la copie de la base de build (Alma 9) exige
#    GLIBC_2.35 (symboles rétroportés par EL9 dans sa glibc 2.34, ABSENTS des
#    glibc ≥ 2.34 pures — Fedora 35-36…). Comme les wheels manylinux, on utilise
#    la libgcc_s du SYSTÈME cible : présente partout (base install), toujours
#    cohérente avec sa glibc. Le filtre équivalent est dans les .spec (obligé
#    pour la CLI onefile, dont l'archive échappe à l'audit objdump).
# 2. Embarque libcairo.so.2 + sa fermeture ldd : cairocffi dlopen libcairo.so.2
#    au runtime (aperçu GUI, core/convert_service.py:180) — invisible de
#    l'analyse PyInstaller. On ne touche jamais à ce que PyInstaller a déjà
#    collecté, et on exclut le socle glibc (jamais distribuable).
#
# Usage : bundle_compat.sh [dest]   (défaut : dist/PixelToPath/_internal)
set -euo pipefail

DEST="${1:-dist/PixelToPath/_internal}"
mkdir -p "$DEST"

# ── 1. libgcc_s : jamais embarquée ──
if [ -e "$DEST/libgcc_s.so.1" ]; then
    rm -f "$DEST"/libgcc_s.so.1
    echo "bundle_compat: libgcc_s.so.1 retirée (celle du système cible sera utilisée)"
fi

# ── 2. cairo + fermeture de dépendances ──
CAIRO="$(ldconfig -p | awk '/libcairo\.so\.2/{print $NF; exit}')"
if [ -z "$CAIRO" ]; then
    echo "bundle_compat: libcairo.so.2 introuvable (dnf install cairo)" >&2
    exit 1
fi

# Socle glibc + dl openeur : jamais embarqués (liés à la glibc du système cible).
is_core() {
    case "$(basename "$1")" in
        ld-linux*|libc.so*|libm.so*|libpthread*|libdl*|librt*|libresolv*|\
        libresolv-*|libnsl*|libutil*|libgcc_s.so*|libstdc++.so*|linux-vdso*) return 0 ;;
        *) return 1 ;;
    esac
}

copied=0
while read -r lib path; do
    [ -n "$path" ] || continue
    is_core "$lib" && continue
    dest="$DEST/$(basename "$lib")"
    if [ -e "$dest" ]; then
        continue    # déjà collecté par PyInstaller : on n'écrase pas
    fi
    cp -L "$path" "$dest"
    copied=$((copied + 1))
done < <(ldd "$CAIRO" | awk '
    /=> \//  { print $1, $3 ; next }   # lib.so => /chemin
    /^\//    { print $1, $1 }          # /chemin (ld-linux sans « => »)
')

echo "bundle_compat: ${copied} bibliothèque(s) ajoutée(s) dans $DEST (cairo + dépendances)"
