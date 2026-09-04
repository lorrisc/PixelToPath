"""Vue Partenaires — partenaire DocuNest, boutiques affiliées et don.

Trois relations différentes, trois blocs : le partenaire (DocuNest —
seule carte en teinte primaire, l'accent de la vue : arguments réels,
accroche tirée au hasard à chaque lancement, carrousel de captures), les
affiliés (boutiques de découpe/gravure laser, clientes naturelles des SVG
produits ici — logo officiel sur pastille blanche, accroche aléatoire
elle aussi) et le don en pied de page. Chaque lien s'ouvre dans le
navigateur.
"""

import webbrowser

import customtkinter as ctk

from core.constants import AFFILIATE_URLS, DOCUNEST_URL, PAYPAL_URL
from core.i18n import t
from core.promos import (
    CRICUT_PROMOS,
    DOCUNEST_PROMOS,
    LIGHTBURN_PROMOS,
    pick,
)
from interface.theme.tokens import pair
from interface.utils import resource_path
from interface.views import View
from interface.widgets.card import Card, GhostButton, SectionHeader
from interface.widgets.carousel import Carousel
from interface.widgets.icons import ctk_logo, ctk_picture
from interface.widgets.scrollframe import ScrollFrame

# (clé d'actif, clé i18n du descriptif) — ce que l'utilisateur VA faire de
# ses SVG sur chaque machine. La clé porte le logo (interface/assets/
# partners) et l'URL (AFFILIATE_URLS). L'ordre suit AFFILIATE_URLS.
AFFILIATES = [
    ("cricut", "partners.affiliate_cricut"),
    ("lightburn", "partners.affiliate_lightburn"),
]
AFFILIATE_PROMOS = {"cricut": CRICUT_PROMOS, "lightburn": LIGHTBURN_PROMOS}

# Points forts — les offres réelles de docunest.app, en en-tête de carte.
DOCUNEST_CHIPS = ("partners.chip_tools", "partners.chip_offline",
                  "partners.chip_lifetime", "partners.chip_trial")

# Carrousel : captures officielles du logiciel (gen_partner_assets.py).
DOCUNEST_SLIDES = (
    ("docunest_1", "partners.slide_1"),
    ("docunest_2", "partners.slide_2"),
    ("docunest_3", "partners.slide_3"),
)


class PromoCard(Card):
    """Carte partenaire : fond en teinte primaire au lieu de surface."""

    def apply_theme(self, tokens: dict) -> None:
        self.configure(fg_color=pair("primary_tint"),
                       border_color=pair("border"))


class PartnersView(View):
    def __init__(self, master, ctx):
        super().__init__(master, ctx)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scroll = ScrollFrame(self, fg_color=pair("bg"))
        scroll.grid(row=0, column=0, sticky="nsew")
        # Colonne de contenu plafonnée à sa largeur naturelle (~770 px, la
        # rangée d'affiliés) et centrée : sans elle, les cartes s'étirent sur
        # toute la fenêtre et la page semble vide. minsize 1100 → jamais
        # rogné.
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=0)
        scroll.grid_columnconfigure(2, weight=1)
        self._scroll = scroll
        self._col = 1

        SectionHeader(scroll, t("partners.title")).grid(
            row=0, column=self._col, sticky="w", pady=(0, 12)
        )

        # Ordre pensé pour la hauteur d'une fenêtre minimale (720 px) :
        # DocuNest puis les affiliés d'abord — le don, moins prioritaire,
        # passe en pied de page pour rester au-dessus de la ligne de
        # flottaison le plus souvent possible.
        self._build_docunest()
        self._build_affiliates()
        self._build_donation()

    def _grid(self, widget, **kw):
        kw.setdefault("column", self._col)
        kw.setdefault("sticky", "ew")
        widget.grid(**kw)

    # ── Construction ──────────────────────────────────────────────────────
    def _text_block(self, parent, title: str, body: str) -> None:
        ctk.CTkLabel(parent, text=title, anchor="w", justify="left",
                     text_color=pair("heading"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            fill="x", anchor="w")
        ctk.CTkLabel(parent, text=body, anchor="w", justify="left",
                     text_color=pair("muted"),
                     font=ctk.CTkFont(size=11), wraplength=560).pack(
            fill="x", anchor="w", pady=(2, 0))

    def _build_donation(self) -> None:
        card = Card(self._scroll)
        self._grid(card, row=5, pady=(12, 12))
        col = ctk.CTkFrame(card, fg_color="transparent")
        col.pack(fill="x", padx=14, pady=14)
        self._text_block(
            col, t("partners.donation_title"), t("partners.donation_body"))
        GhostButton(col, text=t("partners.donate"), width=130, height=32,
                    command=lambda: webbrowser.open(PAYPAL_URL)).pack(
            anchor="w", pady=(10, 0))

    def _build_docunest(self) -> None:
        card = PromoCard(self._scroll)
        self._grid(card, row=1, pady=(0, 16))
        col = ctk.CTkFrame(card, fg_color="transparent")
        col.pack(fill="x", padx=14, pady=14)

        # En-tête : pastille logo + « PARTENAIRE » + titre.
        head = ctk.CTkFrame(col, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, image=ctk_logo("docunest", 40), text="").pack(
            side="left")
        texts = ctk.CTkFrame(head, fg_color="transparent")
        texts.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(texts, text=t("partners.badge"), anchor="w",
                     text_color=pair("primary"),
                     font=ctk.CTkFont(size=10, weight="bold")).pack(
            fill="x", anchor="w")
        ctk.CTkLabel(texts, text=t("partners.docunest_title"),
                     anchor="w", justify="left",
                     text_color=pair("heading"),
                     font=ctk.CTkFont(size=15, weight="bold")).pack(
            fill="x", anchor="w")

        ctk.CTkLabel(
            col, anchor="w", justify="left", text_color=pair("muted"),
            font=ctk.CTkFont(size=11), wraplength=660,
            text=t("partners.docunest_body"),
        ).pack(fill="x", anchor="w", pady=(10, 0))

        chips = ctk.CTkFrame(col, fg_color="transparent")
        chips.pack(fill="x", anchor="w", pady=(10, 0))
        for chip_key in DOCUNEST_CHIPS:
            chip = ctk.CTkFrame(chips, fg_color="transparent", border_width=1,
                                border_color=pair("border"), corner_radius=8)
            chip.pack(side="left", padx=(0, 8))
            ctk.CTkLabel(chip, text=t(chip_key), text_color=pair("heading"),
                         font=ctk.CTkFont(size=10, weight="bold")).pack(
                padx=10, pady=4)

        # Accroche tirée au hasard à chaque lancement (core/promos).
        ctk.CTkLabel(col, anchor="w", justify="left", wraplength=660,
                     text=f"✦  {t(pick(DOCUNEST_PROMOS))}",
                     text_color=pair("primary"),
                     font=ctk.CTkFont(size=11, weight="bold")).pack(
            fill="x", anchor="w", pady=(12, 0))

        # Captures du logiciel : carrousel automatique, points cliquables.
        slides = [
            (ctk_picture(f"interface/assets/partners/{name}.png",
                         (560, 315)), t(caption))
            for name, caption in DOCUNEST_SLIDES
        ]
        Carousel(col, slides).pack(anchor="w", pady=(12, 0))

        cta = ctk.CTkFrame(col, fg_color="transparent")
        cta.pack(fill="x", anchor="w", pady=(14, 0))
        ctk.CTkButton(
            cta, text=t("partners.docunest_cta"), width=230,
            height=32, corner_radius=8,
            command=lambda: webbrowser.open(DOCUNEST_URL)).pack(side="left")
        ctk.CTkLabel(cta, anchor="w", text_color=pair("faint"),
                     font=ctk.CTkFont(size=10),
                     text=t("partners.docunest_cta_note")).pack(
            side="left", padx=(10, 0))

    def _build_affiliates(self) -> None:
        SectionHeader(self._scroll, t("partners.affiliates_title")).grid(
            row=2, column=self._col, sticky="w", pady=(0, 8))
        row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._grid(row, row=3, pady=(0, 4))
        for i in range(2):
            row.grid_columnconfigure(i, weight=1, uniform="shops")
        for i, (key, body_key) in enumerate(AFFILIATES):
            card = Card(row)
            # padx symétrique : uniform égalise colonne + padx, un padx
            # asymétrique donnerait une première carte plus large.
            card.grid(row=0, column=i, sticky="nsew", padx=6)
            col = ctk.CTkFrame(card, fg_color="transparent")
            col.pack(fill="both", expand=True, padx=14, pady=14)
            # Le logo officiel (pastille blanche) tient lieu de titre.
            ctk.CTkLabel(col, image=ctk_logo(key, 36), text="").pack(
                anchor="w")
            ctk.CTkLabel(col, text=t(body_key), anchor="w", justify="left",
                         text_color=pair("muted"),
                         font=ctk.CTkFont(size=11),
                         wraplength=300).pack(fill="x", anchor="w",
                                              pady=(8, 6))
            # Accroche aléatoire, elle aussi renouvelée à chaque lancement.
            ctk.CTkLabel(col, text=f"✦  {t(pick(AFFILIATE_PROMOS[key]))}",
                         anchor="w", justify="left", wraplength=300,
                         text_color=pair("primary"),
                         font=ctk.CTkFont(size=11)).pack(
                fill="x", anchor="w", pady=(0, 10))
            # CTA calé en bas : les deux cartes ont la même hauteur, les
            # boutons restent alignés quel que soit le texte.
            GhostButton(col, text=t("partners.visit"), width=120, height=28,
                        command=lambda k=key:
                        webbrowser.open(AFFILIATE_URLS[k])).pack(
                side="bottom", anchor="w")

        ctk.CTkLabel(self._scroll, justify="left", anchor="w",
                     text=t("partners.affiliate_note"),
                     text_color=pair("faint"),
                     font=ctk.CTkFont(size=10), wraplength=560).grid(
            row=4, column=self._col, sticky="w", pady=(8, 2))

    # ── Thème ─────────────────────────────────────────────────────────────
    def apply_theme(self, tokens: dict) -> None:
        super().apply_theme(tokens)
        self._scroll.configure(fg_color=pair("bg"))
