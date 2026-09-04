"""Accroches promotionnelles (core/promos) et affiliations déclarées."""

import unittest

from core import promos
from core.constants import AFFILIATE_URLS, DOCUNEST_URL
from core.i18n import t


class TestPools(unittest.TestCase):
    def test_pools_non_vides_et_textuels(self):
        for pool in (promos.DOCUNEST_PROMOS, promos.CRICUT_PROMOS,
                     promos.LIGHTBURN_PROMOS):
            self.assertTrue(pool, "pool vide : rien à afficher")
            for message in pool:
                self.assertIsInstance(message, str)
                self.assertTrue(message.strip())

    def test_cles_resolues_dans_la_locale(self):
        # Les pools portent des clés i18n : chacune doit exister dans
        # locales/ — sinon l'affichage retomberait sur la clé brute.
        for pool in (promos.DOCUNEST_PROMOS, promos.CRICUT_PROMOS,
                     promos.LIGHTBURN_PROMOS,
                     ["promo.strip_docunest", "promo.strip_cricut",
                      "promo.strip_lightburn"]):
            for key in pool:
                self.assertNotEqual(t(key), key,
                                    f"clé promo sans traduction : {key}")

    def test_pick_reste_dans_le_pool(self):
        for pool in (promos.DOCUNEST_PROMOS, promos.CRICUT_PROMOS,
                     promos.LIGHTBURN_PROMOS):
            self.assertIn(promos.pick(pool), pool)

    def test_couleurs_de_marque_suffisent_aux_bandeaux(self):
        # PromoStrip lit BRAND_COLORS[brand] : une clé manquante ferait
        # planter l'affichage au premier roulement.
        for brand in ("docunest", "cricut", "lightburn"):
            self.assertIn(brand, promos.BRAND_COLORS)
            self.assertIn(brand, promos.BRAND_NAMES)


class TestStripPromos(unittest.TestCase):
    def test_une_seule_accoche_par_marque(self):
        promos_ = promos.strip_promos()
        self.assertEqual(len(promos_), 3)
        self.assertEqual({p.brand for p in promos_},
                         {"docunest", "cricut", "lightburn"})

    def test_ordre_de_depart_toujours_une_rotation_complete(self):
        # Rotation d'une liste fixe : mêmes éléments, jamais de doublon,
        # quel que soit le point de départ tiré au hasard.
        for _ in range(20):
            promos_ = promos.strip_promos()
            self.assertEqual(len({p.brand for p in promos_}), 3)
            self.assertEqual(len({p.key for p in promos_}), 3)

    def test_liens_valides(self):
        promos_ = promos.strip_promos()
        by_brand = {p.brand: p for p in promos_}
        self.assertEqual(by_brand["docunest"].url, DOCUNEST_URL)
        self.assertEqual(by_brand["cricut"].url,
                         AFFILIATE_URLS["cricut"])
        self.assertEqual(by_brand["lightburn"].url,
                         AFFILIATE_URLS["lightburn"])
        for p in promos_:
            self.assertTrue(p.url.startswith("https://"))


class TestAffiliations(unittest.TestCase):
    def test_silhouette_supprimee(self):
        # Régression : l'affiliation Silhouette a été retirée (page
        # partenaires et bandeau) — elle ne doit plus revenir ici.
        self.assertNotIn("silhouette", AFFILIATE_URLS)
        self.assertEqual(set(AFFILIATE_URLS), {"cricut", "lightburn"})


if __name__ == "__main__":
    unittest.main()
