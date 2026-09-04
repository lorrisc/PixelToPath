"""Sélecteur de langue — liste verticale scrollable avec drapeaux.

Remplace le bouton segmenté : illisible dès ~7 langues (une seule rangée
horizontale), la liste verticale + défilement accueille 20+ locales.
Chaque LanguageRow porte le drapeau (interface/assets/flags/<code>.png,
généré par scripts/gen_flags.py), le nom natif (_meta.name) et une coche
pour la langue active — mêmes états que le rail : teinte au survol,
fond teinté marque quand actif. Le widget est muet : il invoque
on_select(code) ; préférence, chargement i18n et reconstruction restent
dans la vue.
"""

import customtkinter as ctk

from core.i18n import t
from interface.theme.tokens import pair
from interface.widgets.card import Card
from interface.widgets.icons import ctk_flag
from interface.widgets.scrollframe import ScrollFrame

ROW_HEIGHT = 42      # hauteur mesurée d'une ligne (label CTk 28 + pady 14)
VISIBLE_ROWS = 8     # fenêtre fixe : la carte ne pousse pas la vue


class LanguageRow(ctk.CTkFrame):
    """Une langue cliquable : drapeau + nom natif + coche si active."""

    def __init__(self, master, code: str, name: str, selected: bool,
                 command):
        super().__init__(master, fg_color="transparent", corner_radius=6)
        self._code = code
        self._command = command
        self._selected = selected
        self._hover = False

        self.grid_columnconfigure(1, weight=1)

        self._flag = ctk.CTkLabel(self, text="", image=ctk_flag(code))
        self._flag.grid(row=0, column=0, padx=(10, 8), pady=7)
        self._name = ctk.CTkLabel(self, anchor="w", text=name,
                                  font=ctk.CTkFont(size=13),
                                  text_color=pair("muted"))
        self._name.grid(row=0, column=1, sticky="ew", pady=7)
        self._check = ctk.CTkLabel(self, text="✓" if selected else "",
                                   width=22,
                                   font=ctk.CTkFont(size=13, weight="bold"))
        self._check.grid(row=0, column=2, padx=(0, 10), pady=7)

        # Comme RailEntry : le clic passe par tous les enfants.
        for w in (self, self._flag, self._name, self._check):
            w.bind("<Button-1>", lambda _e: self._command(self._code))
            w.configure(cursor="hand2")
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
        self._restyle()

    # ── États ────────────────────────────────────────────────────────────
    def _on_enter(self, _e=None) -> None:
        self._hover = True
        self._restyle()

    def _on_leave(self, _e=None) -> None:
        self._hover = False
        self._restyle()

    def _restyle(self) -> None:
        if self._selected:
            self.configure(fg_color=pair("primary_tint"))
            self._name.configure(text_color=pair("heading"))
            self._check.configure(text_color=pair("primary"))
        else:
            self.configure(
                fg_color=pair("seg_track") if self._hover else "transparent")
            self._name.configure(text_color=pair("muted"))

    def apply_theme(self, tokens: dict) -> None:
        self._restyle()


class LanguagePicker(Card):
    """Carte « langue » : accroche, puis liste verticale scrollable."""

    def __init__(self, master, languages: list[dict], current: str,
                 on_select):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, anchor="w", text=t("app.tagline"),
                     justify="left", wraplength=340,
                     text_color=pair("muted"),
                     font=ctk.CTkFont(size=11)).grid(
            row=0, column=0, sticky="ew", padx=14, pady=(12, 8))

        # CTkScrollableFrame EST le frame de contenu : les lignes se posent
        # directement dedans (piège interne customtkinter).
        rows = ScrollFrame(self, height=VISIBLE_ROWS * ROW_HEIGHT + 10,
                           fg_color="transparent")
        rows.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 8))
        rows.grid_columnconfigure(0, weight=1)
        for i, entry in enumerate(languages):
            LanguageRow(
                rows, entry["code"], entry["name"],
                entry["code"] == current, on_select,
            ).grid(row=i, column=0, sticky="ew", padx=2, pady=1)
