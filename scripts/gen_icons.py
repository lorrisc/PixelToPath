"""Génère les icônes PNG du rail de navigation (variants light/dark).

Les icônes sont dessinées par code pour rester reproductibles et cohérentes
(traits 6 px sur canevas 64 px, fond transparent). Relancer après un changement :

    python scripts/gen_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 64
STROKE = 6
OUT = Path(__file__).resolve().parent.parent / "interface" / "assets" / "icons"

# Couleur des icônes par mode — alignée sur les tokens muted.
COLORS = {
    "light": "#666666",
    "dark": "#93a1b1",
}


def _new() -> Image.Image:
    return Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))


def icon_convert() -> Image.Image:
    """Raster → vecteur : grille 2×2 dont une case est devenue un cercle."""
    img = _new()
    d = ImageDraw.Draw(img)
    m, s, g = 8, 20, 4  # marge, taille de case, écart
    coords = [(m, m), (m + s + g, m), (m, m + s + g)]
    for x, y in coords:
        d.rectangle([x, y, x + s, y + s], outline=(0, 0, 0, 255), width=STROKE)
    d.ellipse(
        [m + s + g, m + s + g, m + 2 * s + g, m + 2 * s + g],
        outline=(0, 0, 0, 255), width=STROKE,
    )
    return img


def icon_batch() -> Image.Image:
    """Trois couches empilées (conversion en série)."""
    img = _new()
    d = ImageDraw.Draw(img)
    for i, y in enumerate((12, 27, 42)):
        d.rounded_rectangle([10, y, 54, y + 10], radius=5, outline=(0, 0, 0, 255), width=STROKE - 2)
    return img


def icon_hotfolder() -> Image.Image:
    """Dossier + point en découpe (surveillance)."""
    img = _new()
    mask = Image.new("L", (SIZE, SIZE), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([8, 16, 56, 52], radius=6, fill=255)
    md.rounded_rectangle([8, 10, 26, 22], radius=4, fill=255)
    # Barre de séparation + point : découpes transparentes
    md.rectangle([8, 24, 56, 29], fill=0)
    md.ellipse([25, 35, 39, 49], fill=0)
    solid = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))
    solid.putalpha(mask)
    return solid


def icon_partners() -> Image.Image:
    """Cœur plein (soutenir le projet)."""
    img = _new()
    mask = Image.new("L", (SIZE, SIZE), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([6, 10, 32, 36], fill=255)
    md.ellipse([32, 10, 58, 36], fill=255)
    md.polygon([(7, 26), (57, 26), (32, 56)], fill=255)
    solid = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))
    solid.putalpha(mask)
    return solid


def icon_sun() -> Image.Image:
    img = _new()
    d = ImageDraw.Draw(img)
    d.ellipse([20, 20, 44, 44], outline=(0, 0, 0, 255), width=STROKE)
    import math
    cx = cy = SIZE / 2
    for a in range(0, 360, 45):
        r1, r2 = 27, 34
        x1, y1 = cx + r1 * math.cos(math.radians(a)), cy + r1 * math.sin(math.radians(a))
        x2, y2 = cx + r2 * math.cos(math.radians(a)), cy + r2 * math.sin(math.radians(a))
        d.line([x1, y1, x2, y2], fill=(0, 0, 0, 255), width=STROKE - 1)
    return img


def icon_settings() -> Image.Image:
    """Engrenage — même grammaire que le soleil : anneau + 8 dents radiales,
    œil central plus fin."""
    img = _new()
    d = ImageDraw.Draw(img)
    import math
    cx = cy = SIZE / 2
    d.ellipse([17, 17, 47, 47], outline=(0, 0, 0, 255), width=STROKE)
    for a in range(0, 360, 45):
        r1, r2 = 19, 26
        x1, y1 = cx + r1 * math.cos(math.radians(a)), cy + r1 * math.sin(math.radians(a))
        x2, y2 = cx + r2 * math.cos(math.radians(a)), cy + r2 * math.sin(math.radians(a))
        d.line([x1, y1, x2, y2], fill=(0, 0, 0, 255), width=STROKE)
    d.ellipse([27, 27, 37, 37], outline=(0, 0, 0, 255), width=STROKE - 2)
    return img


def icon_moon() -> Image.Image:
    img = _new()
    mask = Image.new("L", (SIZE, SIZE), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([10, 6, 58, 54], fill=255)
    cut = Image.new("L", (SIZE, SIZE), 0)
    cd = ImageDraw.Draw(cut)
    cd.ellipse([22, 0, 70, 48], fill=255)
    mask.paste(0, (0, 0), cut)
    solid = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))
    solid.putalpha(mask)
    return solid


ICONS = {
    "convert": icon_convert,
    "batch": icon_batch,
    "hotfolder": icon_hotfolder,
    "partners": icon_partners,
    "settings": icon_settings,
    "sun": icon_sun,
    "moon": icon_moon,
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, build in ICONS.items():
        src = build()
        alpha = src.getchannel("A")
        for mode, color in COLORS.items():
            out = Image.new("RGBA", src.size, color)
            out.putalpha(alpha)
            out.save(OUT / f"{name}_{mode}.png")
        print(f"{name}: light + dark écrits dans {OUT}")


if __name__ == "__main__":
    main()
