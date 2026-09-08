"""Détection automatique du preset intégré adapté à une image.

Module pur, sans GUI ni thread : `detect_preset()` classe une image PIL en
« bw » (trait, deux tons), « poster » (peu de couleurs plates) ou « photo »
(le reste) d'après deux mesures bon marché sur une vignette de 256 px —
bimodalité de l'histogramme de luminance et saturation moyenne, puis
dénombrement des couleurs après quantification.

L'image passée en argument n'est JAMAIS mutée : la vignette part d'un
`convert("RGBA")` (tampon privé, gère aussi P/L/CMYK) avant le
`thumbnail()` in-place — appelable depuis un thread worker pendant que la
thread GUI partage l'objet.
"""

from PIL import Image, ImageStat

_THUMB = 256            # côté max de la vignette analysée
_BW_TOP2_MIN = 0.88     # part des 2 bins de luminance dominants (16 bins)
_BW_SAT_MAX = 0.10      # saturation moyenne max pour conclure « deux tons »
_POSTER_COLORS = 16     # au plus ce nombre de couleurs plates → poster
_QUANT_COLORS = 32      # palette demandée à MEDIANCUT avant dénombrement


def detect_preset(pil_image: Image.Image) -> str:
    """Rend "bw", "poster" ou "photo" pour l'image PIL donnée.

    L'ordre des règles importe : un logo bicolore antialiasé a des bords
    gris (bins intermédiaires) mais reste bw ; un logo à trois couleurs
    plates peut atteindre un top2 élevé en luminance, la saturation le
    sort de bw ; une rampe de gris multi-tonalités n'est PAS du trait.
    """
    # Vignette privée : convert() copie avant le thumbnail() in-place.
    thumb = pil_image.convert("RGBA")
    thumb.thumbnail((_THUMB, _THUMB), Image.BILINEAR)

    # Aplat sur blanc (cohérent avec flatten_to_gray du service) : un fond
    # transparent ne doit ni compter comme couleur ni fuiter en saturation.
    flat = Image.new("RGB", thumb.size, (255, 255, 255))
    flat.paste(thumb, mask=thumb.getchannel("A"))

    if _is_bw(flat):
        return "bw"
    if _is_poster(flat):
        return "poster"
    return "photo"


def _is_bw(flat: Image.Image) -> bool:
    """Deux tons : l'histogramme de luminance replié en 16 bins uniformes
    est dominé par ses deux plus gros bins, et la saturation est faible."""
    hist = flat.convert("L").histogram()          # 256 bins
    total = sum(hist)
    if total <= 0:
        return False
    bins = [0] * 16
    for value, count in enumerate(hist):
        bins[value * 16 // 256] += count
    top2 = sum(sorted(bins, reverse=True)[:2]) / total
    sat = ImageStat.Stat(flat.convert("HSV")).mean[1] / 255
    return top2 >= _BW_TOP2_MIN and sat <= _BW_SAT_MAX


def _is_poster(flat: Image.Image) -> bool:
    """Peu de couleurs plates : après quantification MEDIANCUT, l'image
    entière se ramène à un petit nombre de couleurs distinctes."""
    quant = flat.quantize(colors=_QUANT_COLORS, method=Image.MEDIANCUT)
    # getcolors() : un couple par couleur réellement utilisée — jamais
    # None ici, une palette 32 tons ne peut pas dépasser maxcolors=256.
    return len(quant.getcolors()) <= _POSTER_COLORS
