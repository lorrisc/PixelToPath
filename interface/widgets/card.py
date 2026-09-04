"""Carte, en-tête de section et bouton fantôme — la grammaire visuelle commune."""

import customtkinter as ctk

from interface.theme.tokens import pair


class Card(ctk.CTkFrame):
    """Surface surélevée : fond surface + bordure 1 px (jamais d'ombre)."""

    def __init__(self, master, **kw):
        super().__init__(
            master,
            fg_color=pair("surface"),
            border_width=1,
            border_color=pair("border"),
            corner_radius=8,
            **kw,
        )

    def apply_theme(self, tokens: dict) -> None:
        # pair() et non tokens[] : re-stamper la paire [light, dark], sinon
        # configure(fige un hex et les bascules suivantes ne s'appliquent plus.
        self.configure(fg_color=pair("surface"), border_color=pair("border"))


class SectionHeader(ctk.CTkLabel):
    """Micro-titre de section : majuscules, petit, gras, couleur muted."""

    def __init__(self, master, text: str, **kw):
        super().__init__(
            master,
            text=text.upper(),
            text_color=pair("muted"),
            font=ctk.CTkFont(size=11, weight="bold"),
            **kw,
        )

    def apply_theme(self, tokens: dict) -> None:
        self.configure(text_color=pair("muted"))


class GhostButton(ctk.CTkButton):
    """Action secondaire : transparent + bordure 1 px, teinte au survol."""

    def __init__(self, master, **kw):
        super().__init__(
            master,
            fg_color="transparent",
            border_width=1,
            border_color=pair("border"),
            text_color=pair("muted"),
            text_color_disabled=pair("faint"),
            hover_color=pair("primary_tint"),
            corner_radius=8,
            **kw,
        )

    def apply_theme(self, tokens: dict) -> None:
        self.configure(
            border_color=pair("border"),
            text_color=pair("muted"),
            text_color_disabled=pair("faint"),
            hover_color=pair("primary_tint"),
        )
