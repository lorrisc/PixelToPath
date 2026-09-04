"""Vue Paramètres — langue, thème, licence, à propos.

Langue : LanguagePicker (liste verticale scrollable, drapeaux) sur les
locales disponibles (locales/*.json). La sélection enregistre la
préférence puis invoque le rappel de reconstruction de l'app — les vues
sont recréées dans la nouvelle langue, le rail et la barre d'état
re-traduits en place. Ce rappel est invoqué EN DERNIER : la
reconstruction détruit cette vue sous ses pieds.

Thème : Clair/Sombre délégué à App.set_theme (no-op si identique) —
même chemin que le bouton du rail, préférence et icône restent synchrones.

Licence : badge d'état, clé masquée, dates, « Gérer la licence… » ouvre
le LicenseDialog (adaptatif activer/désactiver) — au retour, le rappel
Pro du shell resynchronise rail et vues verrouillées, la section se
rafraîchit. À propos : nom, version, mention.
"""

import webbrowser
from datetime import datetime

import customtkinter as ctk

from core import i18n
from core.i18n import t
from core.constants import APP_NAME, APP_VERSION, LS_CHECKOUT_URL
from interface.theme.tokens import ThemeService, pair
from interface.views import View
from interface.widgets.card import Card, GhostButton, SectionHeader
from interface.widgets.dialogs import LicenseDialog
from interface.widgets.language_picker import LanguagePicker


def _date_fr(iso: str) -> str:
    """Date ISO → %d/%m/%Y, « — » si vide/illisible (idiome dialogs)."""
    try:
        return datetime.fromisoformat(iso or "").strftime("%d/%m/%Y")
    except ValueError:
        return "—"


class SettingsView(View):
    def __init__(self, master, ctx, on_language_change=None,
                 on_theme_change=None, on_pro_change=None):
        super().__init__(master, ctx)
        self._on_language_change = on_language_change
        self._on_theme_change = on_theme_change
        self._on_pro_change = on_pro_change

        self.grid_columnconfigure(0, weight=5, uniform="cols")
        self.grid_columnconfigure(1, weight=4, uniform="cols")
        self.grid_rowconfigure(1, weight=1)

        SectionHeader(self, t("settings.title")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self._build_left()
        self._build_right()

    # ── Construction ──────────────────────────────────────────────────────
    def _build_left(self) -> None:
        col = ctk.CTkFrame(self, fg_color="transparent")
        col.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        col.grid_columnconfigure(0, weight=1)

        SectionHeader(col, t("settings.language")).grid(
            row=0, column=0, sticky="w", pady=(0, 8))
        LanguagePicker(col, i18n.available_languages(),
                       i18n.current_language(), self._on_language).grid(
            row=1, column=0, sticky="ew")

        SectionHeader(col, t("settings.theme")).grid(
            row=2, column=0, sticky="w", pady=(14, 8))
        theme_card = Card(col)
        theme_card.grid(row=3, column=0, sticky="ew")
        theme_card.grid_columnconfigure(0, weight=1)
        # Libellés capturés à la construction (traduits) — jamais comparés
        # à un littéral ; la vue est reconstruite au changement de langue.
        self._theme_modes = {
            t("settings.theme_light"): "light",
            t("settings.theme_dark"): "dark",
        }
        seg_theme = ctk.CTkSegmentedButton(
            theme_card, values=list(self._theme_modes),
            command=self._on_theme)
        seg_theme.grid(row=0, column=0, sticky="ew", padx=14, pady=14)
        seg_theme.set(t("settings.theme_dark" if ThemeService.is_dark()
                        else "settings.theme_light"))

    def _build_right(self) -> None:
        col = ctk.CTkFrame(self, fg_color="transparent")
        col.grid(row=1, column=1, sticky="nsew")
        col.grid_rowconfigure(3, weight=1)
        col.grid_columnconfigure(0, weight=1)

        SectionHeader(col, t("settings.license")).grid(
            row=0, column=0, sticky="w", pady=(0, 8))
        license_card = Card(col)
        license_card.grid(row=1, column=0, sticky="ew")
        license_card.grid_columnconfigure(0, weight=1)
        # Corps reconstruit à chaque changement d'état de licence.
        self._license_body = ctk.CTkFrame(license_card,
                                          fg_color="transparent")
        self._license_body.grid(row=0, column=0, sticky="ew")
        self._refresh_license()

        SectionHeader(col, t("settings.about")).grid(
            row=2, column=0, sticky="w", pady=(14, 8))
        about_card = Card(col)
        about_card.grid(row=3, column=0, sticky="new")
        about_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(about_card, anchor="w",
                     text=f"{APP_NAME} {APP_VERSION}",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=pair("heading")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 0))
        ctk.CTkLabel(about_card, anchor="w", text=t("app.tagline"),
                     text_color=pair("muted"),
                     font=ctk.CTkFont(size=11)).grid(
            row=1, column=0, sticky="w", padx=14, pady=(2, 0))
        ctk.CTkLabel(about_card, anchor="w", text=t("settings.about_line"),
                     text_color=pair("faint"),
                     font=ctk.CTkFont(size=10)).grid(
            row=2, column=0, sticky="w", padx=14, pady=(2, 12))

    # ── Licence (corps reconstruit) ───────────────────────────────────────
    def _refresh_license(self) -> None:
        for child in self._license_body.winfo_children():
            child.destroy()
        pro = self.ctx.license.is_pro()
        key = self.ctx.license.stored_key()

        badge = ctk.CTkLabel(
            self._license_body, anchor="w",
            text=t("license.pro") if pro else t("license.free"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=pair("success") if pro else pair("muted"))
        badge.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))

        row = 1
        if pro:
            ctk.CTkLabel(self._license_body, anchor="w",
                         text=t("license.masked",
                                tail=key[-4:] if len(key) >= 4 else ""),
                         font=ctk.CTkFont(size=13),
                         text_color=pair("heading")).grid(
                row=row, column=0, sticky="w", padx=14, pady=(2, 0))
            row += 1
            config = self.ctx.config
            ctk.CTkLabel(self._license_body, anchor="w", text_color=pair("muted"),
                         font=ctk.CTkFont(size=11),
                         text=t("license.activated_at", date=_date_fr(
                             config.get("pro", "activated_at", "")))).grid(
                row=row, column=0, sticky="w", padx=14, pady=(2, 0))
            row += 1
            ctk.CTkLabel(self._license_body, anchor="w", text_color=pair("muted"),
                         font=ctk.CTkFont(size=11),
                         text=t("license.last_validated", date=_date_fr(
                             config.get("pro", "last_validated_at", "")))).grid(
                row=row, column=0, sticky="w", padx=14, pady=(2, 0))
            row += 1

        GhostButton(self._license_body, text=t("license.manage"),
                    width=160, height=30,
                    command=self._open_license_dialog).grid(
            row=row, column=0, sticky="w", padx=14, pady=(10, 0))
        row += 1
        if not pro:
            GhostButton(self._license_body, text=t("license.buy"),
                        width=160, height=30,
                        command=lambda: webbrowser.open(
                            LS_CHECKOUT_URL)).grid(
                row=row, column=0, sticky="w", padx=14, pady=(6, 12))
        else:
            # Respire : le corps reste aéré avec ou sans le lien d'achat.
            ctk.CTkLabel(self._license_body, text="").grid(
                row=row, column=0, pady=(0, 12))

    def _open_license_dialog(self) -> None:
        LicenseDialog(self, self.ctx, on_changed=self._on_license_changed)

    def _on_license_changed(self) -> None:
        # Le shell resynchronise rail + vues verrouillées + surveillance,
        # puis la section reflète le nouvel état.
        if self._on_pro_change is not None:
            self._on_pro_change()
        self._refresh_license()

    # ── Sélections ────────────────────────────────────────────────────────
    def _on_language(self, code: str) -> None:
        if code not in {e["code"] for e in i18n.available_languages()}:
            return
        if code == i18n.current_language():
            return
        self.ctx.config.set("general", "language", code)
        i18n.load_language(code)
        # EN DERNIER : la reconstruction détruit cette vue.
        if self._on_language_change is not None:
            self._on_language_change()

    def _on_theme(self, name: str) -> None:
        mode = self._theme_modes.get(name)
        if mode is not None and self._on_theme_change is not None:
            self._on_theme_change(mode)

    # ── Cycle de vie ──────────────────────────────────────────────────────
    def on_show(self) -> None:
        # La licence peut avoir changé depuis (rail, vue verrouillée).
        self._refresh_license()
