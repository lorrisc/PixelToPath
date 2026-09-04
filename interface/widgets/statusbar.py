"""Barre d'état basse — fil d'information de toute l'application.

Un seul point de vérité pour l'état (set_status) : spinner animé en mode
occupé, couleur par type, bouton Focus à droite (pattern existant, Esc).
"""

import customtkinter as ctk

from core.i18n import t
from interface.theme.tokens import pair
from interface.widgets.card import GhostButton

_SPINNER = ["◐", "◓", "◑", "◒"]
_INTERVAL_MS = 130

# couleur de token par type de statut
_KIND_COLOR = {"idle": "muted", "busy": "text", "ok": "success", "error": "error"}


class StatusBar(ctk.CTkFrame):
    HEIGHT = 36

    def __init__(self, master, on_focus_toggle):
        super().__init__(master, height=self.HEIGHT, corner_radius=0,
                         fg_color=pair("rail"))
        self.grid_propagate(False)
        self._on_focus_toggle = on_focus_toggle

        self.columnconfigure(1, weight=1)

        self._spinner = ctk.CTkLabel(self, text="", width=18,
                                     text_color=pair("primary"),
                                     font=ctk.CTkFont(size=13))
        self._spinner.grid(row=0, column=0, padx=(14, 0), sticky="nsw")

        self._text = ctk.CTkLabel(
            self, text=t("status.ready"), anchor="w", text_color=pair("muted"),
            font=ctk.CTkFont(size=11),
        )
        self._text.grid(row=0, column=1, padx=(8, 12), sticky="nsw")

        self._focus_btn = GhostButton(
            self, text=t("status.focus"), width=110, height=24,
            font=ctk.CTkFont(size=11), command=on_focus_toggle,
        )
        self._focus_btn.grid(row=0, column=2, padx=12, pady=6, sticky="nse")

        self._spin_job = None
        self._spin_index = 0
        self._kind = "idle"
        self._focus_active = False

        # Liseré haut séparant la barre du contenu.
        self._edge = ctk.CTkFrame(self, height=1, corner_radius=0,
                                  fg_color=pair("border"))
        self._edge.place(x=0, rely=0, relwidth=1, anchor="nw")

    # ── API ──────────────────────────────────────────────────────────────
    def set_status(self, text: str, kind: str = "idle") -> None:
        """kind ∈ idle | busy | ok | error."""
        self._kind = kind if kind in _KIND_COLOR else "idle"
        self._text.configure(text=text, text_color=pair(_KIND_COLOR[self._kind]))
        if kind == "busy":
            self._start_spin()
        else:
            self._stop_spin()

    def set_focus_active(self, active: bool) -> None:
        self._focus_active = active
        self._focus_btn.configure(
            text=t("status.focus_exit") if active else t("status.focus"))

    def retranslate(self) -> None:
        """Changement de langue à chaud : libellés re-résolus. Les textes
        transitoires (états publiés par les vues) reviendront dans la
        nouvelle langue à l'événement suivant."""
        self.set_focus_active(self._focus_active)
        self.set_status(t("status.ready"), "idle")

    # ── Spinner ──────────────────────────────────────────────────────────
    def _start_spin(self) -> None:
        if self._spin_job is not None:
            return
        self._tick_spin()

    def _stop_spin(self) -> None:
        if self._spin_job is not None:
            self.after_cancel(self._spin_job)
            self._spin_job = None
        self._spinner.configure(text="")

    def _tick_spin(self) -> None:
        self._spinner.configure(text=_SPINNER[self._spin_index])
        self._spin_index = (self._spin_index + 1) % len(_SPINNER)
        self._spin_job = self.after(_INTERVAL_MS, self._tick_spin)

    # ── Thème ────────────────────────────────────────────────────────────
    def apply_theme(self, tokens: dict) -> None:
        # pair() partout : ne jamais figer un hex simple (sinon la bascule
        # suivante ne s'applique plus au widget).
        self.configure(fg_color=pair("rail"))
        self._edge.configure(fg_color=pair("border"))
        self._spinner.configure(text_color=pair("primary"))
        self._text.configure(text_color=pair(_KIND_COLOR[self._kind]))
