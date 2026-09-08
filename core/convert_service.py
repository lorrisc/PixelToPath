"""Service de conversion image → SVG — sans GUI.

Point unique partagé par l'interface, le batch, le hot folder et la CLI :
préparation de l'image binaire, conversion, rendu cairosvg de l'aperçu.
Aucun import customtkinter ici.

Deux moteurs, choisis par « colormode » dans convert_file() :
- « color » → vtracer (vecteurs couleur par couches) ;
- « binary » → Potrace exclusivement (via potracer, port pur Python) —
  tracé noir/blanc, coordonnées déjà en pixels image (y vers le bas).
"""

import os
import queue
import sys
import tempfile
import threading
import uuid

from PIL import Image, ImageOps

# cairosvg (Linux/Windows) a besoin du runtime GTK embarqué côté Windows.
if sys.platform == "win32":
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    gtk_bin = os.path.join(base, "bin", "gtk-bin")
    if os.path.isdir(gtk_bin):
        os.environ["PATH"] = gtk_bin + os.pathsep + os.environ.get("PATH", "")

# vtracer 0.6.15 (roues cp314) : tout appel à mots-clés segfault sur
# Python 3.14 (pyo3 0.19 pré-3.14, amont visioncortex/vtracer#124) ;
# l'appel positionnel, lui, est sain. On passe donc par la position, dans
# l'ordre exact du .pyi, avec les défauts du crate pour les manquants.
# moteur/image_utils.py reste inchangé (ses PRESETS servent de données).
import vtracer

_VTRACER_ORDER = (
    "colormode", "hierarchical", "mode", "filter_speckle",
    "color_precision", "layer_difference", "corner_threshold",
    "length_threshold", "max_iterations", "splice_threshold",
    "path_precision",
)
_VTRACER_DEFAULTS = dict(
    colormode="color", hierarchical="stacked", mode="spline",
    filter_speckle=4, color_precision=6, layer_difference=16,
    corner_threshold=60, length_threshold=4.0, max_iterations=10,
    splice_threshold=45, path_precision=8,
)

# Potrace (port potracer) : défauts du crate C d'origine, turnpolicy laissé
# à sa valeur MINORITY. Le noir (gris < 50 %) est toujours la partie tracée.
_POTRACE_DEFAULTS = dict(turdsize=2, alphamax=1.0, opttolerance=0.2)


def new_temp_path(temp_dir: str, ext: str) -> str:
    """Chemin unique dans le dossier temporaire de l'application."""
    return os.path.join(temp_dir, f"{uuid.uuid4().hex}{ext}")


def flatten_to_gray(pil_image: Image.Image) -> Image.Image:
    """Aplatit sur fond blanc puis passe en niveau de gris — le noir est
    la partie tracée par le moteur binaire, quelle que soit l'entrée
    (alpha, transparence, couleurs)."""
    img = pil_image.convert("RGBA")
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    return bg.convert("L")


def prepare_input(
    pil_image: Image.Image,
    temp_dir: str,
    colormode: str = "color",
    invert: bool = False,
) -> str:
    """Prépare le PNG passé au moteur ; renvoie son chemin temporaire.

    En mode binaire : aplatit sur fond blanc puis niveau de gris
    (inversion optionnelle) — même traitement que la v2. L'inversion
    reste faite ICI et jamais dans convert_file : les deux doivent
    rester composables sans s'annuler.
    """
    img = pil_image.convert("RGBA")
    if colormode == "binary":
        img = flatten_to_gray(pil_image).convert("RGB")
        if invert:
            img = ImageOps.invert(img)
    tmp = new_temp_path(temp_dir, ".png")
    img.save(tmp, "PNG")
    return tmp


def convert_file(input_path: str, output_path: str, params: dict) -> None:
    """Convertit un fichier raster en SVG (kwargs bruts du moteur).

    Noir et blanc (`colormode == "binary"`) → Potrace exclusivement ;
    couleur → vtracer, dont les kwargs sont réordonnés en positionnel :
    voir la note vtracer/pyo3 en tête de module.
    """
    if params.get("colormode", "color") == "binary":
        _convert_potrace(input_path, output_path, params)
    else:
        full = {**_VTRACER_DEFAULTS, **params}
        vtracer.convert_image_to_svg_py(
            input_path, output_path, *(full[k] for k in _VTRACER_ORDER)
        )


# ── Moteur binaire : Potrace ─────────────────────────────────────────────────
def _potrace_args(params: dict) -> dict:
    """Kwargs Bitmap.trace() d'après les réglages, avec translation des
    anciens kwargs vtracer binaires : les presets personnalisés enregistrés
    avant l'arrivée de Potrace (« filter_speckle », « corner_threshold »,
    « mode »…) doivent rester convertibles. Traductions approximatives —
    l'aire vtracer (côté px) devient une aire potrace (px²), l'angle de
    seuil devient l'alphamax normalisé, « polygon »/« none » forcent les
    angles vifs."""
    args = {k: params[k] for k in _POTRACE_DEFAULTS if k in params}
    if "turdsize" not in args and "filter_speckle" in params:
        args["turdsize"] = max(2, int(params["filter_speckle"]) ** 2)
    if "alphamax" not in args:
        if params.get("mode") in ("polygon", "none"):
            args["alphamax"] = 0.0
        elif "corner_threshold" in params:
            args["alphamax"] = round(
                min(1.334, float(params["corner_threshold"]) / 90), 3)
    return {**_POTRACE_DEFAULTS, **args}


def _convert_potrace(input_path: str, output_path: str, params: dict) -> None:
    """Tracé binaire via potracer (port pur Python de Potrace).

    Import paresseux : la CLI couleur ne charge jamais le module. La
    préparation (aplatissement, inversion) a déjà été faite en amont par
    prepare_input() — ici, on ne fait que seuiller : Bitmap() trace les
    pixels sombres (blacklevel 0.5), le gris est donc passé tel quel.
    """
    import potrace  # potracer

    with Image.open(input_path) as img:
        gray = flatten_to_gray(img)
        width, height = gray.size
    traced = potrace.Bitmap(gray).trace(**_potrace_args(params))
    svg = _potrace_svg(traced, width, height,
                       int(params.get("path_precision", 3)))
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(svg)


def _potrace_svg(path, width: int, height: int, precision: int = 3) -> str:
    """Assemble le SVG potrace : une seule <path> (tous les tracés) en
    fill-rule evenodd — îles et trous sont alors corrects quelle que soit
    l'orientation des sous-chemins. Les coordonnées de potracer sont déjà
    en pixels image, y vers le bas (rectangle en ligne 1 → y = 1, testé)."""
    fmt = f"%.{max(0, precision)}f"
    parts = []
    for curve in path:
        d = [f"M {fmt % curve.start_point.x} {fmt % curve.start_point.y}"]
        for seg in curve:
            if seg.is_corner:
                d.append(f"L {fmt % seg.c.x} {fmt % seg.c.y}")
            else:
                d.append(f"C {fmt % seg.c1.x} {fmt % seg.c1.y}"
                         f" {fmt % seg.c2.x} {fmt % seg.c2.y}")
            d.append(f"{fmt % seg.end_point.x} {fmt % seg.end_point.y}")
        d.append("Z")
        parts.append(" ".join(d))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">\n'
        f'  <path d="{" ".join(parts)}" fill="#000000" '
        f'fill-rule="evenodd" stroke="none"/>\n'
        f'</svg>\n'
    )


def render_svg_to_pil(svg_path: str, output_width: int | None = None) -> Image.Image:
    """Rend un SVG en PIL RGBA (import cairosvg paresseux : la CLI
    convertit sans nécessiter cairosvg). `output_width` sert au
    raffinement du zoom (re-rendu vectoriel à la résolution affichée)."""
    import cairosvg

    tmp = new_temp_path(os.path.dirname(svg_path), ".png")
    try:
        cairosvg.svg2png(url=svg_path, write_to=tmp, output_width=output_width)
        return Image.open(tmp).convert("RGBA")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def next_output_path(directory: str, stem: str) -> str:
    """`stem.svg`, sinon `stem-2.svg`, `stem-3.svg`… (collisions de lot).

    Décidé au moment de la soumission : deux fichiers homonymes de la
    file ne se marchent pas dessus, même si le premier n'est pas encore
    écrit.
    """
    candidate = os.path.join(directory, f"{stem}.svg")
    if not os.path.exists(candidate):
        return candidate
    n = 2
    while os.path.exists(os.path.join(directory, f"{stem}-{n}.svg")):
        n += 1
    return os.path.join(directory, f"{stem}-{n}.svg")


class ConversionWorker:
    """File de conversions traitée sur UNE thread daemon.

    Les moteurs (vtracer, potracer) sont CPU-bound : une seule thread de
    conversion, les items
    s'enchaînent dans l'ordre de soumission. Les résultats partent par
    `(item_id, status, detail)` — status ∈ done | error | cancelled —
    à TOUS les listeners enregistrés (batch et hot folder cohabitent :
    chaque vue préfixe ses item_id et ignore ceux de l'autre), appelés
    DEPUIS la thread : le GUI re-dispatche via after(0).

    cancel_all() agit entre les items : l'item en cours va à son terme,
    les suivants sont signalés « cancelled ». resume() réarme pour un
    nouveau lot.
    """

    def __init__(self, on_result=None, temp_dir: str | None = None):
        self._queue: queue.Queue = queue.Queue()
        self._listeners: list = [on_result] if on_result else []
        self._cancel = threading.Event()
        self._temp_dir = temp_dir or tempfile.gettempdir()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="ptp-worker",
        )
        self._thread.start()

    def add_listener(self, listener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener) -> None:
        """Désabonnement : les vues Pro sont détruites/reconstruites après
        un changement de licence — ne pas y laisser de listener pendant."""
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    def resume(self) -> None:
        self._cancel.clear()

    def submit(self, item_id, input_path: str, output_path: str,
               params: dict) -> None:
        """`params` peut porter « invert » (bool) : l'aplatissement binaire
        inversé est alors fait ici, avant le moteur (l'entrée est un
        fichier, pas une PIL comme dans la vue Convertir)."""
        self._queue.put((item_id, input_path, output_path, dict(params)))

    def cancel_all(self) -> None:
        self._cancel.set()

    def shutdown(self) -> None:
        """Arrêt : la file est vidée (items signalés) puis la thread sort."""
        self._cancel.set()
        while True:
            try:
                item_id = self._queue.get_nowait()[0]
            except queue.Empty:
                break
            self._emit(item_id, "cancelled", "")
        self._queue.put(None)  # sentinelle : fin de la boucle

    def _emit(self, item_id, status: str, detail: str) -> None:
        for listener in self._listeners:
            listener(item_id, status, detail)

    # ── Boucle ────────────────────────────────────────────────────────────
    def _loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            item_id, input_path, output_path, params = item
            if self._cancel.is_set():
                self._emit(item_id, "cancelled", "")
                continue
            tmp_in = input_path
            try:
                if params.get("invert"):
                    with Image.open(input_path) as img:
                        tmp_in = prepare_input(
                            img, self._temp_dir,
                            params.get("colormode", "color"), True)
                convert_file(tmp_in, output_path, params)
                self._emit(item_id, "done", output_path)
            except BaseException as exc:
                # BaseException et non Exception : les paniques pyo3 de
                # vtracer (image illisible, fichier absent…) n'héritent pas
                # d'Exception — elles ne doivent pas tuer la file.
                message = str(exc) or exc.__class__.__name__
                self._emit(item_id, "error", message)
            finally:
                if tmp_in is not input_path:
                    try:
                        os.remove(tmp_in)
                    except OSError:
                        pass
