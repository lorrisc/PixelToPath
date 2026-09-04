"""Migration config v1 → v2 (hotfolder plat → hotfolders[])."""

import json
import tempfile
import unittest
from pathlib import Path

from core.config import ConfigStore, _DEFAULTS, migrate_v1_to_v2

# Forme exacte de la section v1 telle qu'écrite par l'app v3.0 (et telle
# que trouvée dans la config utilisateur au moment de la migration).
V1_SECTION = {
    "watch_dir": "/home/u/Images",
    "output_dir": "/home/u/imgout",
    "preset": "photo",
    "convert_existing": False,
    "enabled": True,
}


def v1_data(hotfolder=None, schema_version=1):
    data = json.loads(json.dumps(_DEFAULTS))
    # _DEFAULTS est déjà v2 : on reproduit un fichier v1 (section plate).
    data.pop("hotfolders", None)
    data.pop("startup", None)
    data["schema_version"] = schema_version
    if hotfolder is not None:
        data["hotfolder"] = hotfolder
    return data


class TestMigrateV1ToV2(unittest.TestCase):
    def test_peuplee_une_entree_verbatim(self):
        data = v1_data(V1_SECTION)
        self.assertTrue(migrate_v1_to_v2(data))
        self.assertEqual(data["schema_version"], 2)
        self.assertNotIn("hotfolder", data)
        folders = data["hotfolders"]
        self.assertEqual(len(folders), 1)
        entry = folders[0]
        # Les cinq champs copiés tels quels…
        for key in V1_SECTION:
            self.assertEqual(entry[key], V1_SECTION[key])
        # …plus id et nom dérivés du dossier.
        self.assertTrue(entry["id"].startswith("hf-"))
        self.assertEqual(entry["name"], "Images")
        self.assertIn("startup", data)
        self.assertFalse(data["startup"]["autostart"])

    def test_vide_liste_vide(self):
        data = v1_data({"watch_dir": "", "output_dir": "", "preset": "bw",
                        "convert_existing": False, "enabled": True})
        self.assertTrue(migrate_v1_to_v2(data))
        self.assertEqual(data["hotfolders"], [])
        self.assertEqual(data["schema_version"], 2)

    def test_absente_liste_vide(self):
        data = v1_data()
        self.assertTrue(migrate_v1_to_v2(data))
        self.assertEqual(data["hotfolders"], [])

    def test_v2_noop(self):
        data = json.loads(json.dumps(_DEFAULTS))
        data["hotfolders"] = [{"id": "hf-x", "name": "N", "watch_dir": "/w",
                               "output_dir": "", "preset": "bw",
                               "convert_existing": False, "enabled": False}]
        before = json.dumps(data, sort_keys=True)
        self.assertFalse(migrate_v1_to_v2(data))
        self.assertEqual(json.dumps(data, sort_keys=True), before)

    def test_version_corrompue_traitee_comme_v1(self):
        data = v1_data(V1_SECTION)
        data["schema_version"] = None
        self.assertTrue(migrate_v1_to_v2(data))
        self.assertEqual(data["schema_version"], 2)


class TestConfigStoreMigration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "config.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_fichier_v1_migre_au_disque(self):
        self.path.write_text(
            json.dumps(v1_data(V1_SECTION)), encoding="utf-8")
        store = ConfigStore(path=self.path)
        self.assertEqual(store.get("schema_version"), 2)
        folders = store.get("hotfolders")
        self.assertEqual(len(folders), 1)
        self.assertEqual(folders[0]["watch_dir"], V1_SECTION["watch_dir"])
        self.assertTrue(folders[0]["enabled"])
        self.assertEqual(store.get("hotfolder") or {}, {})
        # L'id survit à une réouverture (pas de doublon ni de régénération).
        first_id = folders[0]["id"]
        reopened = ConfigStore(path=self.path)
        self.assertEqual(reopened.get("hotfolders")[0]["id"], first_id)

    def test_fichier_corrompu_defauts(self):
        self.path.write_text("{pas du json", encoding="utf-8")
        store = ConfigStore(path=self.path)
        self.assertEqual(store.get("schema_version"), 2)
        self.assertEqual(store.get("hotfolders"), [])

    def test_fichier_absent_defauts_sans_ecriture(self):
        store = ConfigStore(path=self.path)
        self.assertEqual(store.get("hotfolders"), [])
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
