"""HotFolderManager : persistance, cycle de vie, preset, changements à chaud."""

import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image

from core.config import ConfigStore
from core import i18n
from core.hotfolder import HotFolderWatcher
from core.hotfolders import HotFolderManager
from core.presets import PresetController
from moteur.image_utils import PRESETS

HotFolderWatcher.POLL_S = 0.05  # tests : scans rapprochés


class StubWorker:
    def __init__(self):
        self.submitted = []
        self.resumed = 0
        self.listeners = []

    def add_listener(self, fn):
        if fn not in self.listeners:
            self.listeners.append(fn)

    def resume(self):
        self.resumed += 1

    def submit(self, item_id, input_path, output_path, params):
        self.submitted.append((item_id, input_path, output_path, params))


def wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def make_png(path: Path) -> None:
    Image.new("RGB", (8, 8), (200, 30, 30)).save(path)


class ManagerTestCase(unittest.TestCase):
    def setUp(self):
        # Les textes de journal sont assertés en français : la langue par
        # défaut du projet est l'anglais, on charge fr explicitement.
        i18n.load_language("fr")
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.config = ConfigStore(path=self.base / "config.json")
        self.presets = PresetController(self.config)
        self.worker = StubWorker()
        self.manager = HotFolderManager(
            self.config, self.presets, worker_factory=lambda: self.worker)
        self.events = []
        self.manager.add_listener(self.events.append)

    def tearDown(self):
        self.manager.stop_all(persist=False)
        self._tmp.cleanup()

    def add_folder(self, watch_dir=None, **overrides) -> str:
        entry = {
            "name": "Test", "watch_dir": str(watch_dir or self.base / "in"),
            "output_dir": "", "preset": "bw",
            "convert_existing": False, "enabled": False,
        }
        entry.update(overrides)
        return self.manager.add(entry)

    def messages(self) -> list[str]:
        return [e["text"] for e in self.events if e["kind"] == "message"]


class TestPersistance(ManagerTestCase):
    def test_add_update_remove(self):
        fid = self.add_folder()
        entries = self.config.get("hotfolders")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["id"], fid)

        self.assertTrue(self.manager.update(fid, preset="photo", name="B"))
        entry = self.manager.entry(fid)
        self.assertEqual(entry["preset"], "photo")
        self.assertEqual(entry["name"], "B")

        self.manager.remove(fid)
        self.assertEqual(self.config.get("hotfolders"), [])
        self.assertIsNone(self.manager.entry(fid))

    def test_update_inconnu(self):
        self.assertFalse(self.manager.update("hf-nulle", preset="photo"))

    def test_stop_sans_persist_garde_enabled(self):
        (self.base / "in").mkdir()
        fid = self.add_folder(enabled=True)
        self.assertTrue(self.manager.start(fid))
        self.manager.stop(fid, persist=False)
        self.assertFalse(self.manager.running_ids())
        self.assertTrue(self.manager.entry(fid)["enabled"])


class TestCycleDeVie(ManagerTestCase):
    def test_dossier_invalide_refuse(self):
        fid = self.add_folder(watch_dir=self.base / "nullepart")
        self.assertFalse(self.manager.start(fid))
        self.assertIn("introuvable", " ".join(self.messages()))
        self.assertFalse(self.manager.any_running())

    def test_start_stop_persiste_enabled(self):
        watch = self.base / "in"
        watch.mkdir()
        fid = self.add_folder(watch_dir=watch)
        self.assertTrue(self.manager.start(fid))
        self.assertIn(fid, self.manager.running_ids())
        self.assertTrue(self.manager.entry(fid)["enabled"])
        self.assertGreaterEqual(self.worker.resumed, 1)

        self.manager.stop(fid)
        self.assertNotIn(fid, self.manager.running_ids())
        self.assertFalse(self.manager.entry(fid)["enabled"])

    def test_start_all_ne_lance_que_les_actives(self):
        watch = self.base / "in"
        watch.mkdir()
        fid_on = self.add_folder(watch_dir=watch, enabled=True)
        self.add_folder(watch_dir=watch, enabled=False)
        self.assertEqual(self.manager.start_all(), 1)
        self.assertEqual(self.manager.running_ids(), [fid_on])


class TestConversions(ManagerTestCase):
    def test_fichier_stable_soumis_avec_preset_du_dossier(self):
        watch = self.base / "in"
        watch.mkdir()
        fid = self.add_folder(watch_dir=watch, preset="photo")
        self.assertTrue(self.manager.start(fid))

        make_png(watch / "img.png")
        self.assertTrue(
            wait_until(lambda: len(self.worker.submitted) == 1),
            "le fichier stable n'a pas été soumis")
        item_id, input_path, output_path, params = self.worker.submitted[0]
        self.assertEqual(item_id[:2], ("hotfolder", fid))
        self.assertEqual(input_path, str(watch / "img.png"))
        # output_dir vide → à côté de l'image.
        self.assertEqual(output_path, str(watch / "img.svg"))
        self.assertEqual(params, PRESETS["photo"])

    def test_presets_differents_par_dossier(self):
        watch = self.base / "in"
        watch.mkdir()
        fid_a = self.add_folder(watch_dir=watch, preset="bw", enabled=True)
        fid_b = self.add_folder(watch_dir=watch, preset="poster", enabled=True)
        self.assertEqual(self.manager.start_all(), 2)

        make_png(watch / "a.png")
        make_png(watch / "b.png")
        # Les deux watchers partagent le dossier : chacun soumet chaque
        # fichier stable (≥ 2 soumissions, éventuellement 4).
        self.assertTrue(
            wait_until(lambda: len(self.worker.submitted) >= 2))
        by_folder = {s[0][1]: s[3] for s in self.worker.submitted}
        self.assertEqual(by_folder[fid_a], PRESETS["bw"])
        self.assertEqual(by_folder[fid_b], PRESETS["poster"])

    def test_preset_inconnu_repli_bw(self):
        watch = self.base / "in"
        watch.mkdir()
        fid = self.add_folder(watch_dir=watch, preset="custom-supprime")
        self.assertTrue(self.manager.start(fid))

        make_png(watch / "img.png")
        self.assertTrue(
            wait_until(lambda: len(self.worker.submitted) == 1))
        self.assertEqual(self.worker.submitted[0][3], PRESETS["bw"])
        self.assertIn("repli", " ".join(self.messages()))

    def test_resultat_worker_journalise(self):
        watch = self.base / "in"
        watch.mkdir()
        fid = self.add_folder(watch_dir=watch)
        manager = self.manager
        manager._ensure_worker()
        manager._on_worker_result(("hotfolder", fid, 1), "done", "/x/img.svg")
        manager._on_worker_result(("hotfolder", fid, 2), "error", "boom")
        manager._on_worker_result(("batch", 1), "done", "/x/autre.svg")
        texts = self.messages()
        self.assertIn("✓ img.svg", texts)
        self.assertIn("✗ erreur : boom", texts)
        self.assertNotIn("✓ autre.svg", texts)


class TestChangementAChaud(ManagerTestCase):
    def test_output_dir_change_pendant_la_surveillance(self):
        watch = self.base / "in"
        watch.mkdir()
        out2 = self.base / "out2"
        fid = self.add_folder(watch_dir=watch, preset="bw")
        self.assertTrue(self.manager.start(fid))

        self.assertTrue(self.manager.update(fid, output_dir=str(out2)))
        # Redémarrage à chaud visible au journal…
        texts = self.messages()
        self.assertIn("Surveillance arrêtée", texts)
        self.assertIn(f"Surveillance de {watch}", texts)
        self.assertIn(fid, self.manager.running_ids())

        make_png(watch / "img.png")
        self.assertTrue(
            wait_until(lambda: len(self.worker.submitted) == 1))
        self.assertEqual(self.worker.submitted[0][2], str(out2 / "img.svg"))


if __name__ == "__main__":
    unittest.main()
