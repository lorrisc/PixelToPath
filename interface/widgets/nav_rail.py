"""Rail de navigation vertical — icônes + micro-labels, 72 px.

Chaque entrée est un RailEntry : icône CTkImage light/dark, label 10 px,
barre d'indicateur orange 3 px à gauche quand actif. Les entrées Pro
portent une puce « PRO » tant que la licence n'est pas active.
En bas : Paramètres et statut de licence (le thème se règle dans
Paramètres).
"""

import customtkinter as ctk

from core.i18n import t
from interface.theme.tokens import pair
from interface.widgets.icons import ctk_icon

# (clé de vue, clé i18n, icône, réservé Pro) — libellé résolu à la
# construction via t() et re-résolu au changement de langue (retranslate).
NAV_ENTRIES = [
    ("convert", "nav.convert", "convert", False),
    ("batch", "nav.batch", "batch", True),
    ("hotfolder", "nav.hotfolder", "hotfolder", True),
    ("partners", "nav.partners", "partners", False),
]


class RailEntry(ctk.CTkFrame):
    """Entrée cliquable du rail (icône + label, indicateur 3 px)."""

    def __init__(self, master, key: str, label: str, icon: ctk.CTkImage,
                 pro: bool, command):
        super().__init__(master, fg_color="transparent", corner_radius=8)
        self._key = key
        self._command = command
        self._active = False
        self._hover = False

        self.columnconfigure(0, weight=1)

        self._indicator = ctk.CTkFrame(
            self, width=3, corner_radius=2, fg_color="transparent"
        )
        self._indicator.place(x=0, rely=0.5, anchor="w", relheight=0.5)

        self._icon_label = ctk.CTkLabel(self, image=icon, text="")
        self._icon_label.grid(row=0, column=0, pady=(10, 3))
        self._text_label = ctk.CTkLabel(
            self, text=label, font=ctk.CTkFont(size=10),
            text_color=pair("muted"),
        )
        self._text_label.grid(row=1, column=0, pady=(0, 10))

        self._chip = None
        if pro:
            self._chip = ctk.CTkLabel(
                self, text="PRO", corner_radius=4,
                font=ctk.CTkFont(size=8, weight="bold"),
                fg_color=pair("primary"), text_color=pair("on_primary"),
            )
            self._chip.place(relx=1.0, x=-2, y=2, anchor="ne")

        for w in (self, self._icon_label, self._text_label):
            w.bind("<Button-1>", lambda _e, k=key: self._command(k))
            w.configure(cursor="hand2")
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    # ── États ────────────────────────────────────────────────────────────
    def set_active(self, active: bool) -> None:
        self._active = active
        self._restyle()

    def set_label(self, text: str) -> None:
        """Changement de langue à chaud : libellé re-résolu."""
        self._text_label.configure(text=text)

    def set_pro(self, pro: bool) -> None:
        if self._chip is not None:
            self._chip.place_forget() if pro else self._chip.place(
                relx=1.0, x=-2, y=2, anchor="ne"
            )

    # ── Style (actif / survol, résolu depuis les tokens) ─────────────────
    def _on_enter(self, _e=None) -> None:
        self._hover = True
        self._restyle()

    def _on_leave(self, _e=None) -> None:
        self._hover = False
        self._restyle()

    def _restyle(self) -> None:
        t = {
            "primary": pair("primary"),
            "tint": pair("primary_tint"),
            "track": pair("seg_track"),
            "muted": pair("muted"),
            "heading": pair("heading"),
        }
        if self._active:
            self.configure(fg_color=t["tint"])
            self._indicator.configure(fg_color=t["primary"])
            self._text_label.configure(text_color=t["heading"])
        else:
            self.configure(fg_color=t["track"] if self._hover else "transparent")
            self._indicator.configure(fg_color="transparent")
            self._text_label.configure(text_color=t["muted"])

    def apply_theme(self, tokens: dict) -> None:
        self._restyle()
        if self._chip is not None:
            self._chip.configure(
                fg_color=tokens["primary"], text_color=tokens["on_primary"]
            )


class NavRail(ctk.CTkFrame):
    """Colonne de navigation : entrées en haut, licence en bas."""

    WIDTH = 72

    def __init__(self, master, on_select, on_pro_status):
        super().__init__(master, width=self.WIDTH, corner_radius=0,
                         fg_color=pair("rail"))
        self._on_select = on_select
        self._pro = False
        self.grid_propagate(False)

        self.rowconfigure(len(NAV_ENTRIES), weight=1)  # espace souple au milieu
        self.columnconfigure(0, weight=1)

        self._entries: dict[str, RailEntry] = {}
        for row, (key, label_key, icon_name, pro) in enumerate(NAV_ENTRIES):
            entry = RailEntry(
                self, key, t(label_key), ctk_icon(icon_name, 24), pro,
                on_select,
            )
            entry.grid(row=row, column=0, padx=6, pady=2, sticky="ew")
            self._entries[key] = entry

        # Cluster bas : Paramètres, puis séparation, statut licence.
        self._settings_entry = RailEntry(
            self, "settings", t("nav.settings"), ctk_icon("settings", 24),
            False, on_select,
        )
        self._settings_entry.grid(row=len(NAV_ENTRIES) + 1, column=0,
                                  padx=6, pady=2, sticky="ew")

        # Ligne de séparation au-dessus du statut de licence.
        self._divider = ctk.CTkFrame(self, height=1, corner_radius=0,
                                     fg_color=pair("border"))
        self._divider.grid(row=len(NAV_ENTRIES) + 2, column=0,
                           padx=12, pady=(4, 6), sticky="ew")

        self._pro_label = ctk.CTkLabel(
            self, text=t("license.free"), cursor="hand2",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=pair("muted"),
        )
        self._pro_label.grid(row=len(NAV_ENTRIES) + 3, column=0, pady=(0, 12))
        self._pro_label.bind("<Button-1>", lambda _e: on_pro_status())

        # Liseré droit séparant le rail du contenu.
        self._edge = ctk.CTkFrame(self, width=1, corner_radius=0,
                                  fg_color=pair("border"))
        self._edge.place(relx=1.0, rely=0, relheight=1, anchor="ne")

    # ── API ──────────────────────────────────────────────────────────────
    def select(self, key: str) -> None:
        for k, entry in self._entries.items():
            entry.set_active(k == key)
        self._settings_entry.set_active(key == "settings")

    def set_pro(self, pro: bool) -> None:
        self._pro = pro  # drapeau (le texte est traduit : pas de comparaison)
        for entry in self._entries.values():
            entry.set_pro(pro)
        self._pro_label.configure(
            text=t("license.pro") if pro else t("license.free"),
            text_color=pair("success") if pro else pair("muted"),
        )

    def retranslate(self) -> None:
        """Changement de langue à chaud : libellés du rail re-résolus."""
        for key, _label_key, _icon, _pro in NAV_ENTRIES:
            self._entries[key].set_label(t(_label_key))
        self._settings_entry.set_label(t("nav.settings"))
        self.set_pro(self._pro)  # re-résout aussi GRATUIT/PRO

    def apply_theme(self, tokens: dict) -> None:
        # pair() partout : ne jamais figer un hex simple (sinon la bascule
        # suivante ne s'applique plus au widget).
        self.configure(fg_color=pair("rail"))
        self._divider.configure(fg_color=pair("border"))
        self._edge.configure(fg_color=pair("border"))
        if not self._pro:
            self._pro_label.configure(text_color=pair("muted"))
