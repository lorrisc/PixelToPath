"""Accroches promotionnelles — partenaire DocuNest et boutiques affiliées.

Un seul endroit pour les textes affichés sur la page partenaires et le
bandeau de la vue Convertir. Aucune dépendance GUI : chaque vue pioche à
sa construction, soit un tirage par lancement de l'application. Les
promesses reprennent les offres réelles de docunest.app (100 % hors ligne,
26 outils, licence à vie 30 €, essai 7 jours sans carte bancaire).

Les textes sont des CLÉS i18n (promo.*), résolues à l'affichage — jamais
des littéraux : le texte suit la langue courante sans redémarrage.
"""

import random
from dataclasses import dataclass

from core.constants import AFFILIATE_URLS, DOCUNEST_URL

# Couleurs de marque — volontairement invariantes au thème : ce sont des
# identités, pas de l'habillage (relevées sur les logos officiels).
BRAND_COLORS = {
    "docunest": "#0f766e",
    "cricut": "#00a080",
    "lightburn": "#e02020",
}

BRAND_NAMES = {
    "docunest": "DocuNest",
    "cricut": "Cricut",
    "lightburn": "LightBurn",
}

# Page partenaires — un message différent à chaque lancement (clés i18n,
# valeurs dans locales/*.json sous « promo »).
DOCUNEST_PROMOS = [f"promo.docunest_{n}" for n in range(1, 8)]
CRICUT_PROMOS = [f"promo.cricut_{n}" for n in range(1, 4)]
LIGHTBURN_PROMOS = [f"promo.lightburn_{n}" for n in range(1, 4)]


@dataclass(frozen=True)
class Promo:
    """Une accroche affichable : marque, clé i18n du texte, lien à ouvrir."""

    brand: str  # clé d'affiliation : docunest | cricut | lightburn
    key: str    # clé i18n du texte (promo.strip_*), résolue à l'affichage
    url: str


def pick(promos: list[str]) -> str:
    """Un tirage uniforme — appelé une fois par vue, à sa construction."""
    return random.choice(promos)


def strip_promos() -> list[Promo]:
    """Bandeau de la vue Convertir : UNE accroche par marque, le
    roulement passe les trois ; l'ordre de départ varie à chaque
    lancement (rotation d'une liste fixe, jamais de doublon)."""
    promos = [
        Promo("docunest", "promo.strip_docunest", DOCUNEST_URL),
        Promo("cricut", "promo.strip_cricut", AFFILIATE_URLS["cricut"]),
        Promo("lightburn", "promo.strip_lightburn",
              AFFILIATE_URLS["lightburn"]),
    ]
    first = random.randrange(len(promos))
    return promos[first:] + promos[:first]
