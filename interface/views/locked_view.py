"""Vue générique « Fonctionnalité Pro » — affichée tant que pas de licence.

La vraie vue (batch, hot folder) n'est jamais construite sans licence :
le shell remplace simplement l'entrée du rail par celle-ci. Chaque
fonctionnalité décrit ce que débloque Pro (clés license.locked_<slug>_*)
— l'utilisateur gratuit doit savoir précisément ce qu'il achèterait.
"""

import customtkinter as ctk

from core.i18n import t
from interface.theme.tokens import pair
from interface.views import View
from interface.widgets.card import Card, SectionHeader

# Puces « ce que débloque Pro » par fonctionnalité : clés numérotées
# license.locked_<slug>_1..N dans locales/.
DETAIL_LINES = 5


class LockedView(View):
    def __init__(self, master, ctx, feature: str, detail: str = "",
                 on_upgrade=None):
        super().__init__(master, ctx)
        self._on_upgrade = on_upgrade

        # Carte centrée via cellule de grille pondérée (place() ne redimensionne
        # pas fiable le canvas interne des CTkFrame).
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        card = Card(self)
        card.grid(row=0, column=0)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=48, pady=40)

        ctk.CTkLabel(inner, text="🔒", font=ctk.CTkFont(size=36)).pack()
        SectionHeader(inner, feature).pack(pady=(18, 6))
        ctk.CTkLabel(
            inner, justify="center", text_color=pair("muted"),
            text=t("license.locked_line1"),
        ).pack()
        ctk.CTkLabel(
            inner, justify="center", text_color=pair("faint"),
            font=ctk.CTkFont(size=11),
            text=t("license.locked_line2"),
        ).pack(pady=(2, 18))

        if detail:
            SectionHeader(
                inner, t(f"license.locked_{detail}_title"),
            ).pack(pady=(0, 8))
            for i in range(1, DETAIL_LINES + 1):
                row = ctk.CTkFrame(inner, fg_color="transparent")
                row.pack(fill="x", pady=1)
                ctk.CTkLabel(
                    row, text="✓", width=18, text_color=pair("success"),
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).pack(side="left")
                ctk.CTkLabel(
                    row, anchor="w", justify="left", wraplength=430,
                    text_color=pair("muted"),
                    text=t(f"license.locked_{detail}_{i}"),
                ).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            inner, text=t("license.locked_cta"), width=180, height=36,
            command=self._upgrade,
        ).pack(pady=(22, 0))

    def _upgrade(self) -> None:
        if self._on_upgrade is not None:
            self._on_upgrade()
