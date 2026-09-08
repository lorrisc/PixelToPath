"""core/convert_service : dispatch des moteurs et tracé Potrace.

Le noir et blanc doit passer EXCLUSIVEMENT par Potrace (potracer), la
couleur rester sous vtracer — vérifié ici jusqu'au SVG rendu, sans GUI.
"""

import io
import os
import tempfile
import unittest

import cairosvg
import numpy as np
from PIL import Image, ImageOps

from core.convert_service import (
    _potrace_args,
    convert_file,
    prepare_input,
)
from moteur.image_utils import PRESETS


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _square_png(directory: str, size: int = 64, box=(8, 8, 40, 32),
                fill=(10, 10, 10, 255)) -> str:
    """PNG d'essai : carré opaque `box` sur fond transparent."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            img.putpixel((x, y), fill)
    path = os.path.join(directory, "square.png")
    img.save(path, "PNG")
    return path


def _dark_pixels(svg_path: str, size: int = 64) -> np.ndarray:
    """Rend le SVG (cairosvg, aplat sur blanc) et renvoie le masque noir."""
    png = cairosvg.svg2png(bytestring=_read(svg_path).encode("utf-8"),
                           output_width=size, output_height=size)
    bg = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    bg.alpha_composite(Image.open(io.BytesIO(png)).convert("RGBA"))
    return np.array(bg.convert("L")) < 128


class DispatchMoteursTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)
        self.src = _square_png(self.dir)

    def test_binaire_route_vers_potrace(self):
        """binary → SVG Potrace : une seule <path>, evenodd, noirs aux
        positions du carré source (rendu de contrôle)."""
        out = os.path.join(self.dir, "bw.svg")
        convert_file(self.src, out, {"colormode": "binary", "turdsize": 2,
                                     "alphamax": 1.0, "opttolerance": 0.2})
        svg = _read(out)
        self.assertIn("fill-rule=\"evenodd\"", svg)
        self.assertEqual(svg.count("<path"), 1)
        dark = _dark_pixels(out)
        ys, xs = np.where(dark)
        self.assertTrue(ys.size)          # quelque chose est tracé…
        self.assertLess(ys.min(), 20)     # …en haut à gauche…
        self.assertGreater(xs.max(), 30)  # …là où le carré se trouve.

    def test_couleur_reste_vtracer(self):
        """color → vtracer inchangé : une <path> par couche de couleur."""
        img = Image.new("RGB", (64, 64), (255, 255, 255))
        for y in range(8, 32):
            for x in range(8, 40):
                img.putpixel((x, y), (200, 30, 30))
        src = os.path.join(self.dir, "two.png")
        img.save(src, "PNG")
        out = os.path.join(self.dir, "color.svg")
        convert_file(src, out, {"colormode": "color",
                                "hierarchical": "stacked", "mode": "spline",
                                "filter_speckle": 4, "color_precision": 6,
                                "layer_difference": 16,
                                "corner_threshold": 60,
                                "length_threshold": 4.0,
                                "splice_threshold": 45,
                                "max_iterations": 10, "path_precision": 3})
        svg = _read(out)
        self.assertGreaterEqual(svg.count("<path"), 2)  # fond + carré rouge

    def test_preset_bw_est_potrace(self):
        """Le preset intégré « bw » porte les kwargs Potrace et convertit."""
        bw = PRESETS["bw"]
        self.assertEqual(bw["colormode"], "binary")
        for key in ("turdsize", "alphamax", "opttolerance"):
            self.assertIn(key, bw)
        out = os.path.join(self.dir, "bw-preset.svg")
        convert_file(self.src, out, bw)
        self.assertTrue(os.path.exists(out))

    def test_image_blanche_svg_valide(self):
        """Rien à tracer : SVG produit quand même (chemin vide)."""
        img = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
        src = os.path.join(self.dir, "white.png")
        img.save(src, "PNG")
        out = os.path.join(self.dir, "empty.svg")
        convert_file(src, out, PRESETS["bw"])
        svg = _read(out)
        self.assertEqual(svg.count("<path"), 1)
        self.assertFalse(_dark_pixels(out, size=32).any())


class TracePotraceTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def _image_avec_tache(self) -> str:
        """Gros carré + point isolé de 2 px : cobaye du filtre anti-taches."""
        img = Image.new("L", (64, 64), 255)
        for y in range(8, 32):
            for x in range(8, 40):
                img.putpixel((x, y), 20)
        for y in range(50, 52):
            for x in range(50, 52):
                img.putpixel((x, y), 20)
        src = os.path.join(self.dir, "speckle.png")
        img.save(src, "PNG")
        return src

    def _curves(self, path_svg: str) -> int:
        """Chaque tracé potrace commence par « M » dans le d unique."""
        return _read(path_svg).count("M ")

    def test_turdsize_elimine_les_taches(self):
        src = self._image_avec_tache()
        with_turd = os.path.join(self.dir, "turd.svg")
        without = os.path.join(self.dir, "no-turd.svg")
        convert_file(src, with_turd, {"colormode": "binary", "turdsize": 10})
        convert_file(src, without, {"colormode": "binary", "turdsize": 0})
        self.assertEqual(self._curves(with_turd), 1)  # point éliminé
        self.assertEqual(self._curves(without), 2)    # point conservé

    def test_kwargs_vtracer_binaires_legacy(self):
        """Anciens presets personnalisés (kwargs vtracer) translatés."""
        legacy = _potrace_args({"mode": "polygon", "filter_speckle": 4,
                                "corner_threshold": 60})
        self.assertEqual(legacy["turdsize"], 16)     # filter_speckle²
        self.assertEqual(legacy["alphamax"], 0.0)    # polygon → angles vifs
        self.assertEqual(_potrace_args({}),
                         {"turdsize": 2, "alphamax": 1.0,
                          "opttolerance": 0.2})      # défauts Potrace
        modern = _potrace_args({"alphamax": 0.7})
        self.assertEqual(modern["alphamax"], 0.7)    # réglage natif prioritaire

    def test_legacy_convertible_bout_en_bout(self):
        """Un vieux preset binaire vtracer passe intégralement au moteur."""
        out = os.path.join(self.dir, "legacy.svg")
        convert_file(_square_png(self.dir), out,
                     {"colormode": "binary", "mode": "polygon",
                      "filter_speckle": 4, "corner_threshold": 60,
                      "length_threshold": 4.0, "splice_threshold": 45,
                      "max_iterations": 10})
        self.assertGreater(_dark_pixels(out).sum(), 0)

    def test_inversion_faite_en_amont(self):
        """« invert » : seul prepare_input inverse — un carré clair sur fond
        sombre, inversé, trace le carré (flux worker/CLI)."""
        img = Image.new("RGBA", (64, 64), (20, 20, 20, 255))
        for y in range(8, 32):
            for x in range(8, 40):
                img.putpixel((x, y), (240, 240, 240, 255))
        tmp_in = prepare_input(img, self.dir, colormode="binary", invert=True)
        out = os.path.join(self.dir, "inverted.svg")
        convert_file(tmp_in, out, PRESETS["bw"])
        dark = _dark_pixels(out)
        ys, xs = np.where(dark)
        self.assertTrue(ys.size)
        self.assertLess(ys.min(), 20)
        self.assertGreater(xs.max(), 30)
        os.remove(tmp_in)


if __name__ == "__main__":
    unittest.main()
