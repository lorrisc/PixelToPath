"""core/i18n : chargement, repli, format, pluriel, intégration config."""

import json
import tempfile
import unittest
from pathlib import Path

from core import i18n
from core.config import ConfigStore


def _reset() -> None:
    """État de module remis à zéro : chaque test part d'un i18n vierge."""
    i18n._LANGS.clear()
    i18n._lang = ""
    i18n._warned.clear()


def _write_locale(directory: Path, code: str, data: dict) -> None:
    (directory / f"{code}.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")


class I18nTestCase(unittest.TestCase):
    def setUp(self):
        _reset()
        self.addCleanup(_reset)
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

        # Locales synthétiques : le repli « en » + « fr » (règle plurielle
        # n <= 1) + un « zz » minimal — contenu identique pour en et fr.
        for code in ("en", "fr"):
            _write_locale(self.dir, code, {
                "_meta": {"name": "Français" if code == "fr" else "English"},
                "nav": {"convert": "Convertir"},
                "app": {"hidden_done": {"one": "{n} conversion", "other": "{n} conversions"}},
            })
        _write_locale(self.dir, "zz", {
            "_meta": {"name": "Zzz"},
            "nav": {"convert": "Konverti"},
        })

    def test_chargement_et_selection(self):
        self.assertTrue(i18n.load_language("zz", str(self.dir)))
        self.assertEqual(i18n.current_language(), "zz")
        self.assertEqual(i18n.t("nav.convert"), "Konverti")

    def test_repli_sur_defaut_puis_cle(self):
        i18n.load_language("zz", str(self.dir))
        # Absent de « zz » → valeur du repli (en).
        self.assertEqual(i18n.t("app.hidden_done", n=2), "2 conversions")
        # Absent partout → la clé elle-même.
        self.assertEqual(i18n.t("nav.inexistant"), "nav.inexistant")

    def test_langue_inconnue_refuse(self):
        self.assertFalse(i18n.load_language("qq", str(self.dir)))

    def test_pluriel_francais(self):
        i18n.load_language("fr", str(self.dir))
        self.assertEqual(i18n.tp("app.hidden_done", 0), "0 conversion")
        self.assertEqual(i18n.tp("app.hidden_done", 1), "1 conversion")
        self.assertEqual(i18n.tp("app.hidden_done", 2), "2 conversions")

    def test_pluriel_anglais_espagnol(self):
        _write_locale(self.dir, "en", {"items": {"one": "{n} item", "other": "{n} items"}})
        i18n.load_language("en", str(self.dir))
        self.assertEqual(i18n.tp("items", 0), "0 items")
        self.assertEqual(i18n.tp("items", 1), "1 item")
        self.assertEqual(i18n.tp("items", 2), "2 items")

    def test_pluriel_n_injecte(self):
        _write_locale(self.dir, "yy", {"n_files": {"one": "{n} file", "other": "{n} files"}})
        i18n.load_language("yy", str(self.dir))
        self.assertEqual(i18n.tp("n_files", 3), "3 files")

    def test_auto_init_en_sans_install(self):
        # t() doit fonctionner même sans load_language : la langue par
        # défaut (en) est chargée automatiquement à la première recherche.
        self.assertEqual(i18n.t("nav.convert"), "Convert")


class TestLocaleProjet(unittest.TestCase):
    """Le fr.json du projet doit rester cohérent (parse, _meta, pluriels)."""

    def setUp(self):
        _reset()
        self.addCleanup(_reset)

    def _raw(self) -> dict:
        path = Path(i18n._resource_path("locales")) / "fr.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _flatten(self, node, prefix=""):
        res = set()
        for k, v in node.items():
            if k.startswith("_"): continue
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict) and "one" not in v and "other" not in v:
                res.update(self._flatten(v, key))
            else:
                res.add(key)
        return res

    def test_all_locales_parse_and_meta(self):
        locales_dir = Path(i18n._resource_path("locales"))
        for path in locales_dir.glob("*.json"):
            with self.subTest(file=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                self.assertIn("_meta", raw)
                self.assertIn("name", raw["_meta"])

    def test_all_locales_no_duplicate_keys(self):
        locales_dir = Path(i18n._resource_path("locales"))
        for path in locales_dir.glob("*.json"):
            with self.subTest(file=path.name):
                duplicates = []
                def hook(pairs):
                    keys = [k for k, _ in pairs]
                    if len(keys) != len(set(keys)):
                        duplicates.append(keys)
                    return dict(pairs)
                json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=hook)
                self.assertEqual(duplicates, [], f"Clé dupliquée dans {path.name}")

    def test_all_locales_plurals_well_formed(self):
        locales_dir = Path(i18n._resource_path("locales"))
        for path in locales_dir.glob("*.json"):
            with self.subTest(file=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                def walk(node):
                    if isinstance(node, dict):
                        if "one" in node or "other" in node:
                            self.assertIn("one", node)
                            self.assertIn("other", node)
                        else:
                            for value in node.values():
                                walk(value)
                walk(raw)

    def test_all_locales_completeness(self):
        locales_dir = Path(i18n._resource_path("locales"))
        fr_raw = json.loads((locales_dir / "fr.json").read_text(encoding="utf-8"))
        fr_keys = self._flatten(fr_raw)
        
        for path in locales_dir.glob("*.json"):
            if path.name == "fr.json": continue
            with self.subTest(file=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                keys = self._flatten(raw)
                missing = fr_keys - keys
                extra = keys - fr_keys
                self.assertEqual(missing, set(), f"Clés manquantes dans {path.name}: {missing}")
                self.assertEqual(extra, set(), f"Clés en trop dans {path.name}: {extra}")

    def test_messages_hotfolder_invariants(self):
        # Tests de test_hotfolders.py : les textes du journal sont assertés.
        i18n.load_language("fr")
        self.assertEqual(i18n.t("hotfolder.msg.done", name="img.svg"), "✓ img.svg")
        self.assertEqual(i18n.t("hotfolder.msg.error", detail="boom"),
                         "✗ erreur : boom")
        self.assertIn("repli",
                      i18n.t("hotfolder.msg.preset_fallback", key="x", fallback="y"))
        self.assertIn("introuvable",
                      i18n.t("hotfolder.msg.folder_missing", dir="/x"))


class TestConfigLangue(unittest.TestCase):
    def setUp(self):
        _reset()
        self.addCleanup(_reset)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config = ConfigStore(path=Path(self._tmp.name) / "config.json")

    def test_defaut_en(self):
        self.assertEqual(i18n.install_from_config(self.config), "en")
        self.assertEqual(i18n.current_language(), "en")

    def test_code_inconnu_repli_en(self):
        self.config.set("general", "language", "qq")
        self.assertEqual(i18n.install_from_config(self.config), "en")

    def test_lit_la_langue_config(self):
        # fr est la seule locale du projet : zz est simulé en créant le
        # fichier dans locales/ à la volée (répertoire réel du projet).
        locales = Path(i18n._resource_path("locales"))
        (locales / "zz_test.json").write_text(
            json.dumps({"_meta": {"name": "Zzz"}, "x": "y"},
                       ensure_ascii=False), encoding="utf-8")
        self.addCleanup(lambda: (locales / "zz_test.json").unlink())
        self.config.set("general", "language", "zz_test")
        self.assertEqual(i18n.install_from_config(self.config), "zz_test")
        self.assertEqual(i18n.current_language(), "zz_test")


if __name__ == "__main__":
    unittest.main()
