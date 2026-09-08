"""Licence Pro — décisions locales de LicenseManager (réseau simulé).

`_post` est remplacé par un doublon : on teste les décisions (persister,
purger, laisser en grâce), pas le réseau. Règle d'or vérifiée partout :
aucune réponse serveur (hors-ligne) ne délogue l'état local — seule une
invalidité formelle purge.
"""

import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from core.config import ConfigStore
from core.licensing import LicenseManager

KEY = "AAAA-BBBB-CCCC-DDDD-EEEE"


def _days_ago(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).isoformat(
        timespec="seconds")


class LicenseTestCase(unittest.TestCase):
    """Config isolée + manager synchrone (scheduler=None : callback inline)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "config.json"
        self.config = ConfigStore(path=self.path)
        self.manager = LicenseManager(self.config)

    def fake_server(self, response, ok=True):
        """Remplace `_post` : la « réponse » est servie pour tout endpoint."""
        self.manager._post = lambda endpoint, payload: (ok, response)

    def stamp(self, **ages):
        """Écrit des horodatages vieillis : stamp(activated_at=40)."""
        for key, days in ages.items():
            self.config.set("pro", key, _days_ago(days))

    def activate_offline_free(self):
        """État Pro en place sans toucher au réseau (horodatages frais)."""
        self.config.set("pro", "license_key", KEY)
        self.config.set("pro", "instance_id", "inst-1")
        self.stamp(activated_at=0, last_validated_at=0)

    def assert_pro(self, expected: bool):
        self.assertEqual(self.manager.is_pro(), expected)


class TestIsPro(LicenseTestCase):
    def test_vierge_pas_pro(self):
        self.assert_pro(False)

    def test_activation_fraiche_pro(self):
        self.activate_offline_free()
        self.assert_pro(True)

    def test_grace_29_jours_depuis_activation(self):
        self.config.set("pro", "license_key", KEY)
        self.stamp(activated_at=29, last_validated_at=29)
        self.assert_pro(True)

    def test_grace_expirée_depuis_activation(self):
        self.config.set("pro", "license_key", KEY)
        self.stamp(activated_at=31, last_validated_at=31)
        self.assert_pro(False)

    def test_grace_ancrée_sur_la_dernière_validation(self):
        # Le correctif : activé il y a 40 jours mais validé il y a 10 —
        # la grâce court depuis le dernier succès, pas depuis l'activation.
        self.config.set("pro", "license_key", KEY)
        self.stamp(activated_at=40, last_validated_at=10)
        self.assert_pro(True)

    def test_grace_expirée_malgré_une_vieille_validation(self):
        self.config.set("pro", "license_key", KEY)
        self.stamp(activated_at=90, last_validated_at=31)
        self.assert_pro(False)

    def test_cle_sans_horodatage_pas_pro(self):
        # État forgé à la main : clé seule ne suffit jamais.
        self.config.set("pro", "license_key", KEY)
        self.assert_pro(False)

    def test_horodatages_frais_sans_cle_pas_pro(self):
        self.stamp(activated_at=0, last_validated_at=0)
        self.assert_pro(False)


class TestActivate(LicenseTestCase):
    def test_succes_persiste_l_etat(self):
        self.fake_server({"activated": True,
                          "instance": {"id": "inst-42"}})
        result = []
        self.manager.activate(KEY, lambda r: result.append(r))
        ok, _ = result[0]
        self.assertTrue(ok)
        self.assertEqual(self.manager.stored_key(), KEY)
        self.assertEqual(self.config.get("pro", "instance_id"), "inst-42")
        self.assert_pro(True)

    def test_refus_serveur_ne_persiste_pas(self):
        self.fake_server({"activated": False})
        result = []
        self.manager.activate(KEY, lambda r: result.append(r))
        ok, _ = result[0]
        self.assertFalse(ok)
        self.assertEqual(self.manager.stored_key(), "")
        self.assert_pro(False)

    def test_hors_ligne_n_active_pas_et_ne_casse_rien(self):
        self.fake_server({"error": "unreachable"}, ok=False)
        result = []
        self.manager.activate(KEY, lambda r: result.append(r))
        ok, _ = result[0]
        self.assertFalse(ok)
        self.assertEqual(self.manager.stored_key(), "")
        self.assert_pro(False)


class TestValidate(LicenseTestCase):
    def test_hors_ligne_ne_desactive_jamais(self):
        self.activate_offline_free()
        self.fake_server({"error": "unreachable"}, ok=False)
        result = []
        self.manager.validate(lambda r: result.append(r))
        ok, _ = result[0]
        self.assertTrue(ok)  # hors-ligne = succès neutre, jamais une purge
        self.assertEqual(self.manager.stored_key(), KEY)
        self.assert_pro(True)

    def test_valide_active_rafraichit_la_grace(self):
        self.config.set("pro", "license_key", KEY)
        self.stamp(activated_at=40, last_validated_at=40)
        self.assert_pro(False)
        self.fake_server({"valid": True,
                          "license_key": {"status": "active"}})
        result = []
        self.manager.validate(lambda r: result.append(r))
        ok, _ = result[0]
        self.assertTrue(ok)
        self.assert_pro(True)

    def test_cle_desactivee_en_store_purge(self):
        # valid=true mais status != active : la clé a été désactivée en
        # store — l'état local doit disparaître entièrement.
        self.activate_offline_free()
        self.fake_server({"valid": True,
                          "license_key": {"status": "expired"}})
        result = []
        self.manager.validate(lambda r: result.append(r))
        ok, _ = result[0]
        self.assertFalse(ok)
        self.assertEqual(self.manager.stored_key(), "")
        for key in ("instance_id", "activated_at", "last_validated_at"):
            self.assertEqual(self.config.get("pro", key), "")
        self.assert_pro(False)

    def test_reponse_invalide_purge(self):
        self.activate_offline_free()
        self.fake_server({"valid": False})
        result = []
        self.manager.validate(lambda r: result.append(r))
        ok, _ = result[0]
        self.assertFalse(ok)
        self.assertEqual(self.manager.stored_key(), "")
        self.assert_pro(False)


class TestRevalidation(LicenseTestCase):
    def setUp(self):
        super().setUp()
        self.posted = []

    def track_post(self, response, ok=True):
        def _post(endpoint, payload):
            self.posted.append(endpoint)
            return ok, response
        self.manager._post = _post

    def test_pas_de_revalidation_si_recente(self):
        self.activate_offline_free()
        self.track_post({"valid": True, "license_key": {"status": "active"}})
        self.assertFalse(self.manager.maybe_revalidate(lambda _r: None))
        self.assertEqual(self.posted, [])

    def test_revalidation_si_perimee(self):
        self.activate_offline_free()
        self.stamp(last_validated_at=8)
        self.track_post({"valid": True, "license_key": {"status": "active"}})
        self.assertTrue(self.manager.maybe_revalidate(lambda _r: None))
        self.assertEqual(self.posted, ["validate"])

    def test_periodique_retransmet_le_resultat_au_shell(self):
        # Le wiring corrigé : le callback du shell reçoit le résultat de la
        # revalidation hebdomadaire (une purge peut donc basculer l'UI).
        self.activate_offline_free()
        self.stamp(last_validated_at=8)
        self.track_post({"valid": True, "license_key": {"status": "active"}})
        # Scheduler factice : le tick hebdomadaire est seulement enregistré
        # (exécuté à la main ci-dessous), les rebonds « résultat »
        # (after(0) côté app) sont exécutés inline.
        ticks = []

        def scheduler(ms, fn):
            if ms == 0:
                fn()
            else:
                ticks.append(fn)

        self.manager.set_scheduler(scheduler)
        done = threading.Event()
        received = []

        def on_done(result):
            received.append(result)
            done.set()

        self.manager.start_periodic_validation(on_done)
        self.assertEqual(len(ticks), 1)  # premier tick programmé à WEEK_MS
        ticks[0]()
        self.assertTrue(done.wait(2.0), "résultat jamais retransmis")
        self.assertEqual(self.posted, ["validate"])
        self.assertEqual(len(received), 1)
        ok, _message = received[0]
        self.assertTrue(ok)

    def test_periodique_sans_scheduler_noop(self):
        self.manager.start_periodic_validation()  # ne doit rien lever


if __name__ == "__main__":
    unittest.main()
