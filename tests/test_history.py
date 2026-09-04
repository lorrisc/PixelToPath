"""HotFolderHistory : enregistrement, règlement, persistance, cap."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from core.config import ConfigStore
from core.history import HotFolderHistory
from core.hotfolders import HotFolderManager
from core.presets import PresetController
from tests.test_hotfolders import StubWorker, wait_until


class HistoryTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.path = self.base / "history.json"
        self.history = HotFolderHistory(path=self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def store(self) -> HotFolderHistory:
        """Réouvre le fichier : le disque fait foi."""
        return HotFolderHistory(path=self.path)


class TestRecordEtSettle(HistoryTestCase):
    def test_record_puis_settle_done(self):
        self.history.record(("hotfolder", "a", 1), "a", "Photos",
                            "/in/img.png", "/in/img.svg")
        self.history.settle(("hotfolder", "a", 1), "done")
        entries = self.history.entries()
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["folder_id"], "a")
        self.assertEqual(entry["folder_name"], "Photos")
        self.assertEqual(entry["input"], "/in/img.png")
        self.assertEqual(entry["output"], "/in/img.svg")
        self.assertEqual(entry["status"], "done")
        datetime.fromisoformat(entry["ts"])  # timestamp ISO parseable

    def test_plus_recentes_en_tete(self):
        self.history.record(("hotfolder", "a", 1), "a", "A", "/1.png", "/1.svg")
        self.history.settle(("hotfolder", "a", 1), "done")
        self.history.record(("hotfolder", "b", 2), "b", "B", "/2.png", "/2.svg")
        self.history.settle(("hotfolder", "b", 2), "error", "boom")
        entries = self.history.entries()
        self.assertEqual([e["folder_id"] for e in entries], ["b", "a"])
        self.assertEqual(entries[0]["status"], "error")

    def test_settle_inconnu_ignore(self):
        self.history.settle(("hotfolder", "x", 9), "done")
        self.assertEqual(self.history.entries(), [])

    def test_for_folder_filtre(self):
        self.history.record(("hotfolder", "a", 1), "a", "A", "/1.png", "/1.svg")
        self.history.record(("hotfolder", "b", 1), "b", "B", "/2.png", "/2.svg")
        self.assertEqual([e["folder_id"] for e in self.history.for_folder("a")],
                         ["a"])

    def test_clear(self):
        self.history.record(("hotfolder", "a", 1), "a", "A", "/1.png", "/1.svg")
        self.history.clear()
        self.assertEqual(self.history.entries(), [])


class TestPersistance(HistoryTestCase):
    def test_rechargement(self):
        self.history.record(("hotfolder", "a", 1), "a", "A", "/1.png", "/1.svg")
        self.history.settle(("hotfolder", "a", 1), "done")
        self.history.record(("hotfolder", "b", 2), "b", "B", "/2.png", "/2.svg")
        # b reste « pending » : transaction incomplète → droppée au chargement.
        entries = self.store().entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["folder_id"], "a")
        self.assertEqual(entries[0]["status"], "done")

    def test_fichier_absent_ou_corrrompu(self):
        self.base.joinpath("history.json").write_text("{corrompu")
        self.assertEqual(HotFolderHistory(path=self.path).entries(), [])

    def test_cap_rogne_les_plus_anciennes(self):
        history = HotFolderHistory(path=self.path, cap=3)
        for n in range(1, 5):
            history.record(("hotfolder", "a", n), "a", "A", f"/{n}.png",
                           f"/{n}.svg")
            history.settle(("hotfolder", "a", n), "done")
        self.assertEqual([e["input"] for e in history.entries()],
                         ["/4.png", "/3.png", "/2.png"])
        self.assertEqual(len(self.store().entries()), 3)


class TestHooksManager(unittest.TestCase):
    """record() au submit (manager), settle() + événement au résultat."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.config = ConfigStore(path=self.base / "config.json")
        self.presets = PresetController(self.config)
        self.worker = StubWorker()
        self.history = HotFolderHistory(path=self.base / "history.json")
        self.manager = HotFolderManager(
            self.config, self.presets, worker_factory=lambda: self.worker,
            history=self.history)
        self.events = []
        self.manager.add_listener(self.events.append)
        self.manager._ensure_worker()

    def tearDown(self):
        self.manager.stop_all(persist=False)
        self._tmp.cleanup()

    def add_folder(self) -> str:
        return self.manager.add({
            "name": "Test", "watch_dir": str(self.base / "in"),
            "output_dir": "", "preset": "bw",
            "convert_existing": False, "enabled": False,
        })

    def history_events(self) -> list[dict]:
        return [e for e in self.events if e["kind"] == "history"]

    def test_conversion_surveilee_enregistree(self):
        fid = self.add_folder()
        in_path, out_path = str(self.base / "in" / "img.png"), \
            str(self.base / "in" / "img.svg")
        self.manager._on_ready(fid, in_path, out_path)
        self.assertTrue(wait_until(lambda: len(self.worker.submitted) == 1))
        # Enregistré dès la soumission, encore « En cours ».
        self.assertEqual(self.history.entries()[0]["status"], "pending")

        item_id = self.worker.submitted[0][0]
        self.manager._on_worker_result(item_id, "done", out_path)
        entries = self.history.entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["status"], "done")
        self.assertEqual(entries[0]["folder_id"], fid)
        self.assertEqual(entries[0]["folder_name"], "Test")
        # Un événement « history » a annoncé le règlement…
        self.assertTrue(wait_until(lambda: len(self.history_events()) >= 1))
        self.assertEqual(self.history_events()[0]["id"], fid)
        # … et la réouverture retrouve l'entrée (persistée).
        self.assertEqual(len(HotFolderHistory(
            path=self.base / "history.json").entries()), 1)

    def test_ids_batch_hors_historique(self):
        self.manager._on_worker_result(("batch", 1), "done", "/x.svg")
        self.assertEqual(self.history.entries(), [])
        self.assertEqual(self.history_events(), [])

    def test_entree_survit_a_la_suppression_du_dossier(self):
        fid = self.add_folder()
        self.manager._on_ready(fid, "/in/a.png", "/in/a.svg")
        item_id = self.worker.submitted[0][0]
        self.manager._on_worker_result(item_id, "error", "boom")
        self.manager.remove(fid)
        entries = self.history.entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["status"], "error")

    def test_manager_sans_historique_necrit_rien(self):
        manager = HotFolderManager(self.config, self.presets,
                                   worker_factory=lambda: StubWorker())
        manager._ensure_worker()
        manager._on_ready("hf-x", "/in/a.png", "/in/a.svg")
        manager._on_worker_result(("hotfolder", "hf-x", 1), "done", "/in/a.svg")
        self.assertIsNone(manager.history)
        self.assertFalse((self.base / "history.json").exists())


if __name__ == "__main__":
    unittest.main()
