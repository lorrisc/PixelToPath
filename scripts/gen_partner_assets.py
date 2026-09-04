"""Génère les visuels partenaires embarqués (captures DocuNest + badges logos).

Sources — hors embarqué, archives des originaux :
  captures/docunest/docunest_{1,2,3}.png  captures d'écran 1920×1080
  captures/logos/                         logos officiels (svg/png)

Sortie — embarquée par PyInstaller (le spec copie tout interface/) :
  interface/assets/partners/docunest_{1,2,3}.png   1280×720
  interface/assets/partners/logo_{docunest,cricut,lightburn}.png
      logo posé sur une pastille blanche arrondie 300×88 : lisible sur les
      deux thèmes, une seule variante nécessaire.

    python scripts/gen_partner_assets.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SRC_SHOTS = ROOT / "captures" / "docunest"
SRC_LOGOS = ROOT / "captures" / "logos"
OUT = ROOT / "interface" / "assets" / "partners"

# Pastille : 300×88 (affichée à 150×44 — rendue en 2× pour rester nette en
# écran HiDPI), logo centré dans une boîte 260×56.
CHIP = (300, 88)
CHIP_BOX = (260, 56)
CHIP_RADIUS = 20
CHIP_BORDER = (228, 228, 228, 255)


def _shots() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for i in (1, 2, 3):
        img = Image.open(SRC_SHOTS / f"docunest_{i}.png").convert("RGB")
        img.thumbnail((1280, 1280), Image.LANCZOS)
        img.save(OUT / f"docunest_{i}.png", optimize=True)
        print(f"docunest_{i}.png {img.size}")


def _chip(logo: Image.Image) -> Image.Image:
    """Pastille blanche arrondie + logo centré (aucun débordement)."""
    chip = Image.new("RGBA", CHIP, (0, 0, 0, 0))
    d = ImageDraw.Draw(chip)
    d.rounded_rectangle([0, 0, CHIP[0] - 1, CHIP[1] - 1],
                        radius=CHIP_RADIUS, fill=(255, 255, 255, 255),
                        outline=CHIP_BORDER, width=2)
    box_w, box_h = CHIP_BOX
    scale = min(box_w / logo.width, box_h / logo.height)
    size = (round(logo.width * scale), round(logo.height * scale))
    logo = logo.resize(size, Image.LANCZOS)
    chip.alpha_composite(
        logo, ((CHIP[0] - size[0]) // 2, (CHIP[1] - size[1]) // 2))
    return chip


def _docunest_mark(size: int = 96) -> Image.Image:
    """Marque DocuNest redessinée d'après docunest.app/favicon.svg
    (rendu PIL plutôt que cairosvg : aucune dépendance hors venv)."""
    s = size / 32  # viewBox 32×32
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    teal = (15, 118, 110, 255)  # #0f766e, thème du site
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=round(8 * s),
                        fill=teal)
    back = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(back).rounded_rectangle(
        [7 * s, 6 * s, 20 * s, 23 * s], radius=round(2.2 * s),
        fill=(255, 255, 255, int(255 * 0.38)))
    img.alpha_composite(back)
    d.rounded_rectangle([11 * s, 9 * s, 24 * s, 26 * s],
                        radius=round(2.2 * s), fill=(255, 255, 255, 255))
    for x2, y in ((21.5, 15.2), (19.7, 18.6), (20.7, 22)):
        d.line([14.5 * s, y * s, x2 * s, y * s], fill=teal,
               width=round(1.7 * s))
    return img


def _logos() -> None:
    marks = {
        "docunest": _docunest_mark(),
        "cricut": Image.open(SRC_LOGOS / "cricut.png").convert("RGBA"),
        "lightburn": Image.open(SRC_LOGOS / "lightburn.png").convert("RGBA"),
    }
    for name, mark in marks.items():
        chip = _chip(mark)
        chip.save(OUT / f"logo_{name}.png", optimize=True)
        print(f"logo_{name}.png {chip.size}")


if __name__ == "__main__":
    _shots()
    _logos()
