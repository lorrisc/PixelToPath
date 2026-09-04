"""Service de conversion image → SVG — sans GUI.

Point unique partagé par l'interface, le batch, le hot folder et la CLI :
préparation de l'image binaire, conversion vtracer, rendu cairosvg de
l'aperçu. Aucun import customtkinter ici.
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


def new_temp_path(temp_dir: str, ext: str) -> str:
    """Chemin unique dans le dossier temporaire de l'application."""
    return os.path.join(temp_dir, f"{uuid.uuid4().hex}{ext}")


def prepare_input(
    pil_image: Image.Image,
    temp_dir: str,
    colormode: str = "color",
    invert: bool = False,
) -> str:
    """Prépare le PNG passé à vtracer ; renvoie son chemin temporaire.

    En mode binaire : aplatit sur fond blanc puis niveau de gris
    (inversion optionnelle) — même traitement que la v2.
    """
    img = pil_image.convert("RGBA")
    if colormode == "binary":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg.convert("L").convert("RGB")
        if invert:
            img = ImageOps.invert(img)
    tmp = new_temp_path(temp_dir, ".png")
    img.save(tmp, "PNG")
    return tmp


def convert_file(input_path: str, output_path: str, params: dict) -> None:
    """Convertit un fichier raster en SVG (kwargs vtracer bruts).

    Les kwargs sont réordonnés en positionnel : voir la note vtracer/pyo3
    en tête de module.
    """
    full = {**_VTRACER_DEFAULTS, **params}
    vtracer.convert_image_to_svg_py(
        input_path, output_path, *(full[k] for k in _VTRACER_ORDER)
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

    vtracer est CPU-bound : une seule thread de conversion, les items
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
        inversé est alors fait ici, avant vtracer (l'entrée est un fichier,
        pas une PIL comme dans la vue Convertir)."""
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
