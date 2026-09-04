"""Sélecteur de presets — puces horizontales, puce active orange.

Les presets sont la colonne vertébrale du workflow : ce qui est choisi ici
est partagé tel quel (kwargs vtracer bruts) par la vue de conversion, le
batch, le hot folder et la CLI.

Widget muet : émet on_select(nom) ; l'état est piloté par set_options().
"""

import customtkinter as ctk

from core.i18n import t
from interface.theme.tokens import pair


def custom_label() -> str:
    """Libellé de la puce indicateur « réglages divergents » — résolu à
    l'appel (jamais à l'import : le switch de langue reconstruit les vues
    et les appelants passent le même libellé à set_options(active=…))."""
    return t("presets.custom")


class PresetPicker(ctk.CTkFrame):
    def __init__(self, master, on_select, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._on_select = on_select
        self._names: list[str] = []
        self._active: str | None = None
        self._chips: dict[str, ctk.CTkButton] = {}

    # ── API ───────────────────────────────────────────────────────────────
    def set_options(self, names: list[str], active: str | None = None) -> None:
        """Reconstruit la rangée de puces ; `active` sélectionnée sans callback.

        Une puce « Personnalisé » clôt toujours la rangée : indicateur
        d'état (réglages divergents), jamais cliquable.
        """
        custom = custom_label()
        for chip in self._chips.values():
            chip.destroy()
        self._chips.clear()
        self._names = list(names) + [custom]
        self._active = active if active in self._names else None
        for i, name in enumerate(self._names):
            is_custom = name == custom
            chip = ctk.CTkButton(
                self, text=name, width=0, height=30, corner_radius=6,
                font=ctk.CTkFont(size=11, weight="bold"),
                # indicateur : pas de commande, pas de main
                cursor="hand2" if not is_custom else "arrow",
                command=None if is_custom else lambda n=name: self._on_select(n),
            )
            chip.grid(row=0, column=i, padx=(0, 6), sticky="w")
            self._chips[name] = chip
        self._restyle()

    def set_active(self, name: str | None) -> None:
        """Change la puce active sans émettre on_select()."""
        self._active = name
        self._restyle()

    def active(self) -> str | None:
        return self._active

    # ── Style ─────────────────────────────────────────────────────────────
    def _restyle(self) -> None:
        custom = custom_label()
        for name, chip in self._chips.items():
            if name == self._active:
                chip.configure(
                    fg_color=pair("primary"), hover_color=pair("primary_hover"),
                    text_color=pair("on_primary"), border_width=0,
                )
            elif name == custom:
                # inactive : plus discret qu'une action (texte « faint ») ;
                # hover_color n'accepte pas « transparent » → surface.
                chip.configure(
                    fg_color="transparent", hover_color=pair("surface"),
                    text_color=pair("faint"), border_width=1,
                    border_color=pair("border"),
                )
            else:
                chip.configure(
                    fg_color="transparent", hover_color=pair("seg_track"),
                    text_color=pair("muted"), border_width=1,
                    border_color=pair("border"),
                )

    def apply_theme(self, tokens: dict) -> None:
        # pair() et non tokens[] : garder les paires [light, dark] vivantes.
        self._restyle()
