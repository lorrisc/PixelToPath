"""Génère les drapeaux du sélecteur de langue (interface/assets/flags/).

Un PNG par locale (locales/*.json), dessiné par code pour rester
reproductible et cohérent — mêmes principes que gen_icons.py : canevas
4× (96×72) puis réduction LANCZOS, coins arrondis et liseré gris neutre
semi-transparent pour détacher les champs clairs des deux thèmes.
Relancer après l'ajout d'une langue :

    python scripts/gen_flags.py

Le script croise la liste des locales et des drapeaux dessinés : toute
locale sans drapeau (ou l'inverse) est signalée — une nouvelle langue
doit arriver avec son entrée dans FLAGS.
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 96, 72          # canevas de dessin (4× la taille affichée 24×18)
OUT = Path(__file__).resolve().parent.parent / "interface" / "assets" / "flags"
LOCALES = Path(__file__).resolve().parent.parent / "locales"

RADIUS = 12            # coins arrondis (3 px une fois affiché à 24×18)
BORDER = (127, 127, 127, 140)  # liseré neutre : visible en clair et sombre


def _canvas() -> Image.Image:
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def _bands(colors, horizontal=True) -> Image.Image:
    """Bandes égales (3 couleurs = tiers)."""
    img = _canvas()
    d = ImageDraw.Draw(img)
    n = len(colors)
    for i, color in enumerate(colors):
        if horizontal:
            d.rectangle([0, i * H / n, W, (i + 1) * H / n], fill=color)
        else:
            d.rectangle([i * W / n, 0, (i + 1) * W / n, H], fill=color)
    return img


def _weighted_bands(colors, weights, horizontal=True) -> Image.Image:
    """Bandes de hauteurs (ou largeurs) proportionnelles aux poids."""
    img = _canvas()
    d = ImageDraw.Draw(img)
    total = sum(weights)
    offset = 0.0
    for color, weight in zip(colors, weights):
        end = offset + weight / total
        if horizontal:
            d.rectangle([0, offset * H, W, end * H], fill=color)
        else:
            d.rectangle([offset * W, 0, end * W, H], fill=color)
        offset = end
    return img


def _star(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float,
          fill) -> None:
    """Étoile à 5 branches (pointe en haut), rayon intérieur classique."""
    pts = []
    for i in range(10):
        ang = math.radians(-90 + i * 36)
        rr = r if i % 2 == 0 else r * 0.382
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    d.polygon(pts, fill=fill)


# ── Drapeaux ─────────────────────────────────────────────────────────────────
def flag_fr() -> Image.Image:
    return _bands(["#002395", "#FFFFFF", "#ED2939"], horizontal=False)


def flag_de() -> Image.Image:
    return _bands(["#000000", "#DD0000", "#FFCE00"])


def flag_nl() -> Image.Image:
    return _bands(["#AE1C28", "#FFFFFF", "#21468B"])


def flag_ru() -> Image.Image:
    return _bands(["#FFFFFF", "#0039A6", "#D52B1E"])


def flag_es() -> Image.Image:
    return _weighted_bands(["#AA151B", "#F1BF00", "#AA151B"], [1, 2, 1])


def flag_hi() -> Image.Image:
    img = _bands(["#FF9933", "#FFFFFF", "#138808"])
    d = ImageDraw.Draw(img)
    r = H * 0.23
    d.ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r],
              outline="#000080", width=2)
    for a in range(0, 360, 15):  # 24 rayons du chakra
        x = W / 2 + r * math.cos(math.radians(a))
        y = H / 2 + r * math.sin(math.radians(a))
        d.line([W / 2, H / 2, x, y], fill="#000080", width=1)
    return img


def flag_en() -> Image.Image:
    """Union Jack simplifié : diagonales, croix blanche, croix rouge."""
    img = _canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H], fill="#012169")
    for x1, y1, x2, y2 in ((0, 0, W, H), (W, 0, 0, H)):
        d.line([x1, y1, x2, y2], fill="#FFFFFF", width=14)
        d.line([x1, y1, x2, y2], fill="#C8102E", width=5)
    d.rectangle([W / 2 - 11, 0, W / 2 + 11, H], fill="#FFFFFF")
    d.rectangle([0, H / 2 - 11, W, H / 2 + 11], fill="#FFFFFF")
    d.rectangle([W / 2 - 6, 0, W / 2 + 6, H], fill="#C8102E")
    d.rectangle([0, H / 2 - 6, W, H / 2 + 6], fill="#C8102E")
    return img


def flag_pt() -> Image.Image:
    img = _weighted_bands(["#046A38", "#DA291C"], [2, 3], horizontal=False)
    d = ImageDraw.Draw(img)
    x = 2 * W / 5
    d.ellipse([x - 14, H / 2 - 14, x + 14, H / 2 + 14],
              outline="#FFE900", width=3)
    return img


def flag_pt_br() -> Image.Image:
    img = _canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H], fill="#009C3B")
    d.polygon([(6, H / 2), (W / 2, 8), (W - 6, H / 2), (W / 2, H - 8)],
              fill="#FFDF00")
    r = H * 0.2
    d.ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], fill="#002776")
    return img


def flag_ar() -> Image.Image:
    """Arabie saoudite simplifiée : champ vert, chahada et sabre suggérés
    par deux traits blancs."""
    img = _canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H], fill="#006C35")
    # Chahada : ligne ondulée (écriture suggérée, non lisible à cette taille)
    pts = [(26 + i * 11, 28 + (3 if i % 2 else -3)) for i in range(5)]
    d.line(pts, fill="#FFFFFF", width=4, joint="curve")
    # Sabre : trait droit à la pointe triangulaire
    d.line([22, 46, 70, 46], fill="#FFFFFF", width=4)
    d.polygon([(70, 42), (78, 46), (70, 50)], fill="#FFFFFF")
    return img


def flag_bn() -> Image.Image:
    img = _canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H], fill="#006A4E")
    r = H * 0.4
    cx = W * 0.45
    d.ellipse([cx - r, H / 2 - r, cx + r, H / 2 + r], fill="#F42A41")
    return img


def flag_fa() -> Image.Image:
    img = _bands(["#239F40", "#FFFFFF", "#DA0000"])
    d = ImageDraw.Draw(img)
    # Emblème central simplifié (tulipe) : ovale rouge + trait vertical.
    cx, cy, rx, ry = W / 2, H / 2, 6, 11
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill="#DA0000")
    d.line([cx, cy - ry - 4, cx, cy + ry + 4], fill="#DA0000", width=3)
    return img


def flag_ko() -> Image.Image:
    """Taegeuk + quatre trigrammes le long des diagonales."""
    img = _canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H], fill="#FFFFFF")
    cx, cy, r = W / 2, H / 2, H * 0.25
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#CD2E3A")
    d.pieslice([cx - r, cy - r, cx + r, cy + r], 0, 180, fill="#0047A0")
    for color, dx in (("#0047A0", -r / 2), ("#CD2E3A", r / 2)):
        d.ellipse([cx + dx - r / 2, cy - r / 2, cx + dx + r / 2, cy + r / 2],
                  fill=color)
    for theta in (45, 135, 225, 315):
        ux, uy = math.cos(math.radians(theta)), math.sin(math.radians(theta))
        px, py = -uy, ux  # perpendiculaire : direction des barres
        for radius in (r * 1.5, r * 1.85, r * 2.2):
            mx, my = cx + radius * ux, cy + radius * uy
            d.line([mx - 7 * px, my - 7 * py, mx + 7 * px, my + 7 * py],
                   fill="#000000", width=3)
    return img


def flag_ur() -> Image.Image:
    """Pakistan : bande blanche, croissant et étoile."""
    img = _canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H], fill="#01411C")
    d.rectangle([0, 0, W / 4, H], fill="#FFFFFF")
    cx, cy, r = W * 0.60, H * 0.48, H * 0.28
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#FFFFFF")
    dx, dy = r * 0.35, -r * 0.30  # découpe décalée : croissant
    d.ellipse([cx + dx - r * 0.85, cy + dy - r * 0.85,
               cx + dx + r * 0.85, cy + dy + r * 0.85], fill="#01411C")
    _star(d, cx + r * 0.72, cy - r * 0.55, r * 0.30, "#FFFFFF")
    return img


def flag_zh() -> Image.Image:
    img = _canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H], fill="#DE2918")
    _star(d, W * 0.20, H * 0.25, H * 0.18, "#FFDE00")
    for cx, cy in ((W * 0.35, H * 0.10), (W * 0.41, H * 0.21),
                   (W * 0.41, H * 0.33), (W * 0.35, H * 0.44)):
        _star(d, cx, cy, H * 0.06, "#FFDE00")
    return img


FLAGS = {
    "ar": flag_ar,
    "bn": flag_bn,
    "de": flag_de,
    "en": flag_en,
    "es": flag_es,
    "fa": flag_fa,
    "fr": flag_fr,
    "hi": flag_hi,
    "ko": flag_ko,
    "nl": flag_nl,
    "pt": flag_pt,
    "pt_BR": flag_pt_br,
    "ru": flag_ru,
    "ur": flag_ur,
    "zh": flag_zh,
}


def finish(img: Image.Image) -> Image.Image:
    """Arrondit les coins, pose le liseré, réduit à la taille d'affichage 2×."""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, W - 1, H - 1], radius=RADIUS, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    d = ImageDraw.Draw(out)
    d.rounded_rectangle([1, 1, W - 2, H - 2], radius=RADIUS - 1,
                        outline=BORDER, width=2)
    return out.resize((W // 2, H // 2), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for code, build in sorted(FLAGS.items()):
        finish(build()).save(OUT / f"{code}.png")
    # Contrôle de couverture : chaque locale doit avoir son drapeau.
    locale_codes = {p.stem for p in sorted(LOCALES.glob("*.json"))}
    for missing in sorted(locale_codes - set(FLAGS)):
        print(f"[flags] drapeau manquant pour la locale « {missing} »",
              file=__import__("sys").stderr)
    orphans = sorted(set(FLAGS) - locale_codes)
    for orphan in orphans:
        print(f"[flags] drapeau « {orphan} » sans locale — à retirer")
    print(f"{len(FLAGS)} drapeaux écrits dans {OUT}")


if __name__ == "__main__":
    main()
