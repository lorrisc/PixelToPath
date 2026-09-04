"""Vues de l'application — une par entrée du rail.

Contrat : chaque vue hérite de View (master, ctx), reste orchestratrice
(les widgets sont muets) et implémente set_focus_mode si elle réagit au
mode focus. Le shell les instancie paresseusement et les cache jamais
détruites — l'état d'une vue survit à la navigation.
"""

import customtkinter as ctk

from interface.theme.tokens import pair


class View(ctk.CTkFrame):
    """Base des vues : fond bg explicite (jamais « transparent » sous la
    racine Tk, qui cuirait un hex unique et ne basculerait jamais)."""

    def __init__(self, master, ctx):
        super().__init__(master, fg_color=pair("bg"))
        self.ctx = ctx

    def apply_theme(self, tokens: dict) -> None:
        # pair() et non tokens[] : conserver la paire [light, dark] pour que
        # les bascules suivantes restent gérées par customtkinter.
        self.configure(fg_color=pair("bg"))

    def set_focus_mode(self, enabled: bool) -> None:
        """Appelé à l'entrée/sortie du mode focus ; no-op par défaut."""

    def on_show(self) -> None:
        """La vue redevient visible (show_view) : resynchronisation —
        les autres vues ont pu changer presets, licence, surveillance…
        no-op par défaut."""


# Imports en fin de module : les vues héritent de View défini ci-dessus.
from .batch_view import BatchView  # noqa: E402
from .convert_view import ConvertView  # noqa: E402
from .hotfolder_view import HotFolderView  # noqa: E402
from .locked_view import LockedView  # noqa: E402
from .partners_view import PartnersView  # noqa: E402
from .settings_view import SettingsView  # noqa: E402

__all__ = [
    "View",
    "BatchView",
    "ConvertView",
    "HotFolderView",
    "LockedView",
    "PartnersView",
    "SettingsView",
]
