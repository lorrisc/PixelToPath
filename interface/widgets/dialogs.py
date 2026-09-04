"""Dialogues modaux — enregistrement et gestion des presets personnalisés.

Fenêtres thémées via pair() (résolu par ctk au mode courant) : pas de
apply_theme ici, le grab_set bloque le rail pendant l'ouverture — le thème
ne peut pas basculer sous un dialogue modal. Esc est bindé AVANT le grab
pour que la fermeture soit gérée ici et ne remonte pas au focus mode.
"""

import tkinter as tk
import webbrowser
from datetime import datetime

import customtkinter as ctk

from core.constants import LS_CHECKOUT_URL
from core.i18n import t
from core.presets import name_error
from interface.theme.tokens import pair
from interface.widgets.card import GhostButton
from interface.widgets.scrollframe import ScrollFrame


class Dialog(ctk.CTkToplevel):
    """Base : modale centrée sur son parent, Esc / ❌ ferment."""

    def __init__(self, parent, title: str):
        super().__init__(parent)
        self._parent = parent
        self.title(title)
        self.configure(fg_color=pair("bg"))
        self.resizable(False, False)
        self.transient(parent)
        self.withdraw()  # mesurer avant d'apparaître (pas de flash à (0,0))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=20, pady=(18, 16))

        self._ok_btn: ctk.CTkButton | None = None
        self.bind("<Escape>", lambda _e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Return>", lambda _e: self._on_return())

    # ── Cycle de vie ──────────────────────────────────────────────────────
    def open_centered(self) -> None:
        """Une fois le contenu construit : placer, montrer, prendre le grab."""
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        px, py = self._parent.winfo_rootx(), self._parent.winfo_rooty()
        pw, ph = self._parent.winfo_width(), self._parent.winfo_height()
        self.geometry(f"{w}x{h}+{px + max(0, (pw - w) // 2)}"
                      f"+{py + max(0, (ph - h) // 3)}")
        self.deiconify()
        self.after(150, self._grab)

    def _grab(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            pass  # déjà détruite (fermeture immédiate)

    def close(self) -> None:
        self.destroy()

    def _on_return(self) -> None:
        pass  # les sous-classes branchent leur action

    # ── Aides de construction ─────────────────────────────────────────────
    def _buttons(self, action_label: str, command) -> None:
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", side="bottom", pady=(16, 0))
        GhostButton(row, text=t("common.cancel"), width=90, height=32,
                    command=self.close).pack(side="right")
        self._ok_btn = ctk.CTkButton(row, text=action_label, width=118,
                                     height=32, state="disabled",
                                     command=command)
        self._ok_btn.pack(side="right", padx=(0, 8))


class SavePresetDialog(Dialog):
    """Enregistre les réglages courants sous un nouveau nom."""

    def __init__(self, parent, ctx, params: dict, on_saved):
        super().__init__(parent, t("presets.save_title"))
        self._ctx = ctx
        self._params = params
        self._on_saved = on_saved

        ctk.CTkLabel(self.body, text=t("presets.name_label"), anchor="w",
                     text_color=pair("muted"),
                     font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x")
        self._entry = ctk.CTkEntry(self.body, height=34)
        self._entry.pack(fill="x", pady=(6, 4))
        self._error = ctk.CTkLabel(self.body, text="", anchor="w",
                                   text_color=pair("error"),
                                   font=ctk.CTkFont(size=11))
        self._error.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(
            self.body, anchor="w", justify="left", wraplength=330,
            text_color=pair("faint"), font=ctk.CTkFont(size=11),
            text=t("presets.reusable_hint"),
        ).pack(fill="x")

        self._buttons(t("common.save"), self._save)
        self._entry.bind("<KeyRelease>", lambda _e: self._validate())
        self._on_return = self._save
        self.open_centered()
        self.after(80, self._entry.focus_set)

    def _validate(self) -> bool:
        msg = name_error(self._entry.get().strip(),
                         self._ctx.presets.custom_names())
        self._error.configure(text=msg or "")
        self._ok_btn.configure(state="disabled" if msg else "normal")
        return msg is None

    def _save(self) -> None:
        if not self._validate():
            return
        name = self._entry.get().strip()
        if self._ctx.presets.save(name, self._params):
            self._on_saved(name)
            self.close()


class ManagePresetsDialog(Dialog):
    """Renomme ou supprime les presets personnalisés, en direct."""

    def __init__(self, parent, ctx, on_changed):
        super().__init__(parent, t("presets.manage_title"))
        self._ctx = ctx
        self._on_changed = on_changed
        self._confirm: set[str] = set()  # suppressions armées (2 clics)

        self._list = ScrollFrame(self.body, fg_color="transparent",
                                 height=220)
        self._list.pack(fill="both", expand=True)
        GhostButton(self.body, text=t("common.close"), height=32,
                    command=self.close).pack(side="right", pady=(16, 0))
        self._rebuild()
        self.open_centered()

    # ── Contenu ───────────────────────────────────────────────────────────
    def _rebuild(self) -> None:
        for w in self._list.winfo_children():
            w.destroy()
        names = self._ctx.presets.custom_names()
        if not names:
            ctk.CTkLabel(
                self._list, justify="center", text_color=pair("faint"),
                font=ctk.CTkFont(size=12),
                text=t("presets.empty"),
            ).pack(pady=28)
            return
        for name in names:
            self._row(name)

    def _refresh(self) -> None:
        self._confirm.clear()
        self._rebuild()
        self._on_changed()

    def _row(self, name: str) -> None:
        row = ctk.CTkFrame(self._list, fg_color="transparent")
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text=name, anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(
            side="left", fill="x", expand=True)
        rename_btn = GhostButton(row, text=t("common.rename"), width=86,
                                 height=28,
                                 command=lambda: self._edit(row, name))
        rename_btn.pack(side="right")
        del_btn = GhostButton(row, text=t("common.delete"), width=86,
                              height=28,
                              command=lambda: self._delete(name, del_btn))
        del_btn.pack(side="right", padx=(0, 6))

    # ── Suppression (armement en deux clics, pas de modale imbriquée) ─────
    def _delete(self, name: str, btn) -> None:
        if name not in self._confirm:
            self._confirm.add(name)
            btn.configure(text=t("common.confirm"), text_color=pair("error"))
            return
        self._ctx.presets.delete(name)
        self._refresh()

    # ── Renommage en ligne ────────────────────────────────────────────────
    def _edit(self, row, name: str) -> None:
        for w in row.winfo_children():
            w.destroy()
        entry = ctk.CTkEntry(row, height=28)
        entry.pack(side="left", fill="x", expand=True)
        entry.insert(0, name)

        def commit(_event=None):
            self._commit(entry, name)

        ok = GhostButton(row, text=t("common.validate"), width=72, height=28,
                         command=commit)
        ok.pack(side="right", padx=(0, 6))
        GhostButton(row, text=t("common.cancel"), width=72, height=28,
                    command=self._refresh).pack(side="right")
        entry.bind("<Return>", commit)
        entry.bind("<Escape>", lambda _e: self._refresh())
        entry.bind("<KeyRelease>",
                   lambda _e: self._validate_rename(entry, name, ok))
        entry.focus_set()
        entry.icursor("end")

    def _validate_rename(self, entry, current: str, ok_btn) -> bool:
        customs = [n for n in self._ctx.presets.custom_names() if n != current]
        msg = name_error(entry.get().strip(), customs)
        entry.configure(border_color=pair("error") if msg else pair("border"))
        ok_btn.configure(state="disabled" if msg else "normal")
        return msg is None

    def _commit(self, entry, old: str) -> None:
        new = entry.get().strip()
        if new == old:
            self._refresh()
            return
        if self._ctx.presets.rename(old, new):
            self._refresh()


class UpgradeDialog(Dialog):
    """Vente : ce que débloque Pro + CTA checkout (la clé part par e-mail)."""

    # Clés i18n résolues À LA CONSTRUCTION (jamais à l'import : le
    # changement de langue à chaud reconstruirait sinon avec l'ancien texte).
    FEATURES = (
        ("upgrade.feature_batch_title", "upgrade.feature_batch_sub"),
        ("upgrade.feature_hotfolder_title", "upgrade.feature_hotfolder_sub"),
        ("upgrade.feature_cli_title", "upgrade.feature_cli_sub"),
    )

    def __init__(self, parent, ctx, on_changed=None):
        super().__init__(parent, t("license.upgrade_title"))
        self._ctx = ctx
        self._on_changed = on_changed

        ctk.CTkLabel(self.body, text=t("license.upgrade_title"),
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=pair("heading")).pack()
        ctk.CTkLabel(
            self.body, justify="center", text_color=pair("faint"),
            font=ctk.CTkFont(size=11),
            text=t("license.buy_hint"),
        ).pack(pady=(2, 14))

        for title_key, sub_key in self.FEATURES:
            row = ctk.CTkFrame(self.body, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text="✓", width=18, text_color=pair("success"),
                         font=ctk.CTkFont(size=12, weight="bold")).pack(
                side="left")
            col = ctk.CTkFrame(row, fg_color="transparent")
            col.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(col, text=t(title_key), anchor="w",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(
                fill="x")
            ctk.CTkLabel(col, text=t(sub_key), anchor="w",
                         text_color=pair("faint"),
                         font=ctk.CTkFont(size=11)).pack(fill="x")

        ctk.CTkButton(self.body, text=t("license.buy"), width=200, height=36,
                      command=self._buy).pack(pady=(18, 6))
        GhostButton(self.body, text=t("upgrade.have_key"), height=30,
                    command=self._have_key).pack()

        self.open_centered()

    def _buy(self) -> None:
        webbrowser.open(LS_CHECKOUT_URL)

    def _have_key(self) -> None:
        self.close()
        LicenseDialog(self._parent, self._ctx, on_changed=self._on_changed)


class LicenseDialog(Dialog):
    """Activation (coller la clé) ou désactivation de la licence locale."""

    def __init__(self, parent, ctx, on_changed=None):
        super().__init__(parent, t("license.title"))
        self._ctx = ctx
        self._on_changed = on_changed
        self._busy = False

        if ctx.license.is_pro():
            self._build_active()
        else:
            self._build_entry()
        self.open_centered()

    # ── État « pas de licence » : saisie + activation ─────────────────────
    def _build_entry(self) -> None:
        ctk.CTkLabel(self.body, text=t("license.key_label"), anchor="w",
                     text_color=pair("muted"),
                     font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x")
        self._entry = ctk.CTkEntry(self.body, height=34)
        self._entry.pack(fill="x", pady=(6, 4))
        self._status = ctk.CTkLabel(self.body, text="", anchor="w",
                                    text_color=pair("error"),
                                    font=ctk.CTkFont(size=11))
        self._status.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(
            self.body, anchor="w", wraplength=330, text_color=pair("faint"),
            font=ctk.CTkFont(size=11),
            text=t("license.key_hint"),
        ).pack(fill="x")

        self._buttons(t("license.activate"), self._activate)
        self._on_return = self._activate
        self.after(80, self._entry.focus_set)

    def _activate(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._ok_btn.configure(state="disabled")
        self._status.configure(text=t("license.activating"),
                               text_color=pair("faint"))
        self._ctx.license.activate(self._entry.get(), self._on_result)

    # ── État « licence active » : clé masquée + désactivation ─────────────
    def _build_active(self) -> None:
        key = self._ctx.license.stored_key()
        validated = self._ctx.config.get("pro", "last_validated_at", "")
        try:
            date = datetime.fromisoformat(validated).strftime("%d/%m/%Y")
        except ValueError:
            date = "—"

        ctk.CTkLabel(self.body, text=t("license.masked",
                                       tail=key[-4:] if len(key) >= 4 else ""),
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=pair("heading")).pack(pady=(2, 8))
        self._status = ctk.CTkLabel(self.body, anchor="center",
                                    text_color=pair("success"),
                                    font=ctk.CTkFont(size=12, weight="bold"),
                                    text=t("license.active_on_device"))
        self._status.pack(fill="x")
        ctk.CTkLabel(self.body, text_color=pair("faint"),
                     font=ctk.CTkFont(size=11),
                     text=t("license.last_check", date=date)).pack(
            fill="x", pady=(2, 0))

        self._buttons(t("license.deactivate"), self._deactivate)
        self._ok_btn.configure(state="normal")

    def _deactivate(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._ok_btn.configure(state="disabled")
        self._status.configure(text=t("license.deactivating"),
                               text_color=pair("faint"))
        self._ctx.license.deactivate(self._on_result)

    # ── Résultat commun ───────────────────────────────────────────────────
    def _on_result(self, result) -> None:
        ok, message = result
        self._busy = False
        if not self.winfo_exists():
            return  # fermé pendant la requête
        if ok:
            self._status.configure(text=message, text_color=pair("success"))
            if self._on_changed is not None:
                self._on_changed()
            self.after(700, self.close)
        else:
            self._status.configure(text=message, text_color=pair("error"))
            if self._ok_btn is not None:
                self._ok_btn.configure(state="normal")
