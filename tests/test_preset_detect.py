"""core/preset_detect : classement bw / poster / photo d'une image PIL.

Images synthétiques comme test_convert_service — zéro GUI, zéro disque
(les images vivent en mémoire, la détection ne lit que des pixels).
"""

import time
import unittest

import numpy as np
from PIL import Image, ImageFilter

from core.preset_detect import detect_preset


class DetectionPresetTestCase(unittest.TestCase):
    def _bw_logo(self, size=256) -> Image.Image:
        """Logo N&B antialiasé : carré noir flouté sur fond blanc."""
        img = Image.new("RGB", (size, size), (255, 255, 255))
        img.paste((10, 10, 10), (size // 4, size // 4,
                                 3 * size // 4, 3 * size // 4))
        return img.filter(ImageFilter.GaussianBlur(2))

    def test_logo_noir_et_blanc(self):
        """Trait bicolore antialiasé → bw (les bords gris ne déclassent pas)."""
        self.assertEqual(detect_preset(self._bw_logo()), "bw")

    def test_logo_plat_trois_couleurs(self):
        """Trois aplats saturés sur fond blanc → poster, pas bw ni photo."""
        img = Image.new("RGB", (256, 256), (255, 255, 255))
        img.paste((200, 30, 30), (20, 20, 120, 120))
        img.paste((30, 90, 200), (140, 20, 236, 120))
        img.paste((250, 200, 30), (60, 140, 200, 236))
        self.assertEqual(detect_preset(img), "poster")

    def test_photo_degrade_et_bruit(self):
        """Dégradé RGB lissé + bruit → photo (ni bw, ni poster)."""
        rng = np.random.default_rng(7)
        xs = np.linspace(0, 255, 256, dtype=np.float32)
        grad = np.stack(np.meshgrid(xs, xs), axis=-1)[..., :1]
        grad = np.repeat(grad, 3, axis=-1)[:, :, ::-1]  # teinte variable
        noise = rng.integers(0, 60, (256, 256, 3), dtype=np.int16)
        arr = np.clip(grad + noise, 0, 255).astype(np.uint8)
        self.assertEqual(detect_preset(Image.fromarray(arr, "RGB")), "photo")

    def test_rampe_de_gris_pas_bw(self):
        """Gris multi-tonalités : top2 effondré → jamais classée bw."""
        xs = np.linspace(0, 255, 256).astype(np.uint8)
        ramp = Image.fromarray(np.tile(xs, (256, 1)), "L")
        self.assertNotEqual(detect_preset(ramp), "bw")

    def test_image_non_mutee(self):
        """La détection ne touche pas l'objet reçu (thumbnail in-place)."""
        img = self._bw_logo().convert("RGBA")
        before = (img.tobytes(), img.size, img.mode)
        detect_preset(img)
        self.assertEqual((img.tobytes(), img.size, img.mode), before)

    def test_image_minuscule(self):
        """8×8 : thumbnail no-op, aucun chemin ne lève, verdict valide."""
        verdict = detect_preset(Image.new("RGB", (8, 8), (0, 0, 0)))
        self.assertIn(verdict, ("bw", "poster", "photo"))

    def test_performance_grande_image(self):
        """4000×4000 sous ~1,5 s : le coût dominant reste convert+thumbnail."""
        img = self._bw_logo(4000)
        start = time.perf_counter()
        verdict = detect_preset(img)
        elapsed = time.perf_counter() - start
        self.assertEqual(verdict, "bw")
        self.assertLess(elapsed, 1.5)


if __name__ == "__main__":
    unittest.main()
