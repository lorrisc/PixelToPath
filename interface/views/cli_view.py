"""Vue « Ligne de commande » — présentation de la CLI `ptp` (Pro).

Page explicative toujours accessible (à la différence des vues
verrouillées) : l'utilisateur gratuit doit comprendre ce qu'apporte la
CLI avant d'acheter. Aucune logique — les commandes montrées sont
statiques, la CLI vit dans cli.py. Le pied de page suit la licence :
CTA tant que gratuit, confirmation une fois Pro.
"""

import tkinter.font as tkfont

import customtkinter as ctk

from core.i18n import t
from interface.theme.tokens import pair
from interface.views import View
from interface.widgets.card import Card, SectionHeader
from interface.widgets.scrollframe import ScrollFrame

# Puces « ce que débloque Pro » : clés cli_page.f1..N dans locales/.
FEATURE_LINES = 5

# Commandes d'exemple — du code, jamais traduit.
_EXAMPLES = (
    "ptp convert logo.png -o svg/ --preset bw",
    "ptp convert scans/*.png -o svg/ --preset poster --colormode color",
    "ptp convert scan.png -o svg/ --invert --set filter_speckle=8",
    "ptp license status",
)


class CliView(View):
    def __init__(self, master, ctx, on_upgrade=None):
        super().__init__(master, ctx)
        self._on_upgrade = on_upgrade

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Titre + puce PRO (cachée une fois la licence active, comme au rail).
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="w", pady=(0, 12))
        SectionHeader(head, t("cli_page.title")).pack(side="left")
        self._chip = ctk.CTkLabel(
            head, text="PRO", corner_radius=4,
            font=ctk.CTkFont(size=8, weight="bold"),
            fg_color=pair("primary"), text_color=pair("on_primary"),
        )
        self._chip.pack(side="left", padx=(8, 0), pady=(0, 1))

        scroll = ScrollFrame(self, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew")
        inner = scroll  # CTkScrollableFrame EST le frame de contenu

        ctk.CTkLabel(
            inner, anchor="w", justify="left", wraplength=620,
            text_color=pair("muted"), text=t("cli_page.intro"),
        ).pack(fill="x", pady=(2, 16))

        SectionHeader(inner, t("cli_page.unlock_title")).pack(
            fill="x", pady=(0, 8))
        for i in range(1, FEATURE_LINES + 1):
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row, text="✓", width=18, text_color=pair("success"),
                font=ctk.CTkFont(size=12, weight="bold"),
            ).pack(side="left")
            ctk.CTkLabel(
                row, anchor="w", justify="left", wraplength=620,
                text_color=pair("muted"), text=t(f"cli_page.f{i}"),
            ).pack(side="left", fill="x", expand=True)

        SectionHeader(inner, t("cli_page.examples")).pack(
            fill="x", pady=(18, 8))
        card = Card(inner)
        card.pack(fill="x")
        # Famille fixe garantie multi-plateforme (TkFixedFont), enveloppée
        # en CTkFont : customtkinter refuse un tkinter.font.Font brut.
        mono = ctk.CTkFont(
            family=tkfont.nametofont("TkFixedFont").actual("family"), size=12)
        ctk.CTkLabel(
            card, anchor="w", justify="left", text_color=pair("text"),
            font=mono, text="\n".join(_EXAMPLES),
        ).pack(anchor="w", padx=16, pady=12)

        ctk.CTkLabel(
            inner, anchor="w", justify="left", wraplength=620,
            text_color=pair("muted"), text=t("cli_page.note"),
        ).pack(fill="x", pady=(16, 2))
        ctk.CTkLabel(
            inner, anchor="w", justify="left", wraplength=620,
            text_color=pair("faint"), font=ctk.CTkFont(size=11),
            text=t("cli_page.hint"),
        ).pack(fill="x")

        self._footer = ctk.CTkFrame(inner, fg_color="transparent")
        self._footer.pack(fill="x", pady=(14, 4))
        self.on_show()

    # ── Licence ──────────────────────────────────────────────────────────
    def on_show(self) -> None:
        """La licence a pu changer depuis (dialogue, paramètres) : puce et
        pied de page resynchronisés — idempotent, recallé à chaque affichage."""
        pro = self.ctx.is_pro()
        if pro:
            self._chip.pack_forget()
        else:
            self._chip.pack(side="left", padx=(8, 0), pady=(0, 1))
        for child in self._footer.winfo_children():
            child.destroy()
        if pro:
            ctk.CTkLabel(
                self._footer, anchor="w", text_color=pair("success"),
                font=ctk.CTkFont(size=12, weight="bold"),
                text=t("license.active_on_device"),
            ).pack(side="left")
        else:
            ctk.CTkButton(
                self._footer, text=t("license.locked_cta"),
                width=180, height=36, command=self._upgrade,
            ).pack()

    def _upgrade(self) -> None:
        if self._on_upgrade is not None:
            self._on_upgrade()
