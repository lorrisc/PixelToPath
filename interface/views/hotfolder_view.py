"""Vue Hot folder (Pro) — N dossiers surveillés, SVG automatiques.

Orchestration uniquement : la surveillance vit dans HotFolderManager
(ctx.hotfolders, démarrée au lancement de l'app, survit au masquage de
la fenêtre). Cette vue liste les dossiers (une carte chacun : switch,
dossiers, preset), pilote le manager et rejoue le journal à sa
construction — les lignes émises sans vue ouverte n'ont pas été perdues.
"""

import os
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk

from core import autostart
from core.i18n import t
from interface.theme.tokens import pair
from interface.views import View
from interface.widgets.card import Card, GhostButton, SectionHeader
from interface.widgets.preset_picker import PresetPicker
from interface.widgets.scrollframe import ScrollFrame


class HotFolderView(View):
    def __init__(self, master, ctx):
        super().__init__(master, ctx)
        self._cards: dict[str, _FolderCard] = {}
        self._confirm_delete: set[str] = set()
        self._listening = False

        self.grid_columnconfigure(0, weight=5, uniform="cols")
        self.grid_columnconfigure(1, weight=4, uniform="cols")
        self.grid_rowconfigure(1, weight=1)

        SectionHeader(self, t("hotfolder.title")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self._build_folders_column()
        self._build_side_column()

        self._listen(True)
        self._sync_cards()

    # ── Construction ──────────────────────────────────────────────────────
    def _build_folders_column(self) -> None:
        col = ctk.CTkFrame(self, fg_color="transparent")
        col.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        col.grid_rowconfigure(1, weight=1)
        col.grid_columnconfigure(0, weight=1)

        SectionHeader(col, t("hotfolder.folders")).grid(
            row=0, column=0, sticky="w", pady=(0, 8))

        # CTkScrollableFrame EST son propre frame de contenu : les cartes
        # se posent directement dedans (jamais de frame intermédiaire).
        self._list = ScrollFrame(col, fg_color=pair("surface"))
        self._list.grid(row=1, column=0, sticky="nsew")
        self._empty = ctk.CTkLabel(
            self._list, justify="center", text_color=pair("faint"),
            text=t("hotfolder.empty"),
        )
        self._empty.pack(pady=28, fill="x")

        GhostButton(col, text=t("hotfolder.add"),
                    width=210, height=32,
                    command=self._add_folder).grid(
            row=2, column=0, sticky="w", pady=(12, 0))

    def _build_side_column(self) -> None:
        col = ctk.CTkFrame(self, fg_color="transparent")
        col.grid(row=1, column=1, sticky="nsew")
        col.grid_rowconfigure(3, weight=1)
        col.grid_columnconfigure(0, weight=1)

        SectionHeader(col, t("hotfolder.startup")).grid(
            row=0, column=0, sticky="w", pady=(0, 8))
        card = Card(col)
        card.grid(row=1, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        self._build_startup(card)

        SectionHeader(col, t("hotfolder.journal")).grid(
            row=2, column=0, sticky="w", pady=(14, 8))
        log_card = Card(col)
        log_card.grid(row=3, column=0, sticky="nsew")
        log_card.grid_rowconfigure(2, weight=1)
        log_card.grid_columnconfigure(0, weight=1)
        # Switcher Journal (flux live) / Historique (persistant, daté).
        self._tab = ctk.CTkSegmentedButton(
            log_card, values=[t("history.tab"), t("history.title")],
            command=self._on_tab)
        self._tab.set(t("history.tab"))
        self._tab.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))
        self._clear_armed = False
        self._clear_btn = GhostButton(log_card, text=t("history.clear"),
                                      width=110, height=26,
                                      command=self._clear_history)
        self._clear_btn.grid(row=0, column=0, sticky="e", padx=14,
                             pady=(12, 4))
        self._clear_btn.grid_remove()  # l'historique seul se vide

        self._caption = ctk.CTkLabel(
            log_card, text=t("hotfolder.journal_caption"), anchor="w",
            text_color=pair("muted"),
            font=ctk.CTkFont(size=11, weight="bold"))
        self._caption.grid(row=1, column=0, sticky="ew", padx=14, pady=(4, 4))

        # Deux pages dans la même cellule : le ScrollFrame est porté par son
        # canvas interne (grid_remove sur lui ne le cache pas), ce sont donc
        # les pages conteneurs qu'on bascule — jamais le ScrollFrame lui-même.
        self._page_log = ctk.CTkFrame(log_card, fg_color="transparent")
        self._page_log.grid(row=2, column=0, sticky="nsew")
        self._page_log.grid_rowconfigure(0, weight=1)
        self._page_log.grid_columnconfigure(0, weight=1)
        self._page_hist = ctk.CTkFrame(log_card, fg_color="transparent")
        self._page_hist.grid(row=2, column=0, sticky="nsew")
        self._page_hist.grid_rowconfigure(0, weight=1)
        self._page_hist.grid_columnconfigure(0, weight=1)
        self._page_hist.grid_remove()

        self._log = ctk.CTkTextbox(self._page_log, height=200, wrap="none",
                                   fg_color=pair("bg"),
                                   text_color=pair("muted"),
                                   font=ctk.CTkFont(size=11))
        self._log.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        self._log.configure(state="disabled")

        # Historique : liste datée (les lignes se posent directement dedans).
        self._hist = ScrollFrame(self._page_hist, fg_color=pair("bg"))
        self._hist.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        self._refresh_history()

    def _build_startup(self, card: Card) -> None:
        # L'artefact OS fait foi (éditable à la main) : l'état des
        # interrupteurs est relu, pas seulement la config.
        os_enabled = autostart.autostart_enabled()
        minimized = bool(self.ctx.config.get("startup", "start_minimized",
                                             False))

        self._auto_switch = ctk.CTkSwitch(
            card, text=t("hotfolder.autostart"),
            progress_color=pair("primary"), command=self._on_autostart)
        self._auto_switch.grid(row=0, column=0, sticky="w", padx=14,
                               pady=(12, 2))
        if os_enabled:
            self._auto_switch.select()

        self._min_switch = ctk.CTkSwitch(
            card, text=t("hotfolder.start_minimized"),
            progress_color=pair("primary"), command=self._on_start_minimized)
        self._min_switch.grid(row=1, column=0, sticky="w", padx=14, pady=(2, 2))
        if os_enabled and minimized:
            self._min_switch.select()
        self._min_switch.configure(
            state="normal" if os_enabled else "disabled")

        ctk.CTkLabel(card, anchor="w", justify="left", wraplength=300,
                     text_color=pair("faint"), font=ctk.CTkFont(size=10),
                     text=t("hotfolder.autostart_hint")).grid(
            row=2, column=0, sticky="ew", padx=14, pady=(2, 12))

    # ── Cartes (une par dossier) ──────────────────────────────────────────
    def _sync_cards(self) -> None:
        """Recrée/resynchronise les cartes : construction, retour sur
        l'onglet — presets, licence ou surveillance ont pu changer."""
        running = set(self.ctx.hotfolders.running_ids())
        seen = set()
        for entry in self.ctx.hotfolders.entries():
            fid = entry["id"]
            seen.add(fid)
            card = self._cards.get(fid)
            if card is None:
                card = _FolderCard(self._list, self, entry)
                card.pack(fill="x", pady=4, padx=4)
                self._cards[fid] = card
            card.refresh_picker(self._active_display(entry))
            # Reflète l'état sans toucher au manager (select() n'émet pas
            # la commande du switch).
            card.set_running(fid in running)
        for fid in [f for f in self._cards if f not in seen]:
            card = self._cards.pop(fid)
            card.destroy()
        self._refresh_empty()

    def _refresh_empty(self) -> None:
        if self._cards:
            self._empty.pack_forget()
        else:
            self._empty.pack(pady=28, fill="x")

    def _active_display(self, entry: dict) -> str | None:
        """Libellé du preset du dossier, avec repli « Noir & blanc » si la
        clé stockée n'existe plus (preset custom supprimé ailleurs)."""
        presets = self.ctx.presets
        key = entry.get("preset", "bw")
        if presets.params(key) is None:
            key = "bw"
        return presets.display_name(key) if presets.params(key) else None

    def on_show(self) -> None:
        self._sync_cards()
        self._refresh_history()

    def destroy(self) -> None:
        self._listen(False)
        super().destroy()

    def _listen(self, enabled: bool) -> None:
        manager = self.ctx.hotfolders
        if manager is None:
            return
        if enabled and not self._listening:
            manager.add_listener(self._queue_event)
            self._listening = True
        elif not enabled and self._listening:
            manager.remove_listener(self._queue_event)
            self._listening = False

    # ── Actions par dossier ───────────────────────────────────────────────
    def _on_toggle(self, folder_id: str) -> None:
        if folder_id in self.ctx.hotfolders.running_ids():
            self.ctx.hotfolders.stop(folder_id)
            return
        if not self.ctx.hotfolders.start(folder_id):
            card = self._cards.get(folder_id)
            if card is not None:
                card.set_running(False)  # le switch retombe
            self.ctx.status.set_status(
                t("hotfolder.pick_watch_first"), "error")

    def _on_preset(self, folder_id: str, label: str) -> None:
        key = self.ctx.presets.resolve(label)
        if key is None:
            return
        self.ctx.hotfolders.update(folder_id, preset=key)
        # Retour visuel immédiat : le picker est muet, la vue pilote l'état
        # — sans ce set_active la puce cliquée ne s'allume jamais.
        card = self._cards.get(folder_id)
        if card is not None:
            card.picker.set_active(label)

    def _pick_watch(self, folder_id: str) -> None:
        d = filedialog.askdirectory(parent=self, title=t("hotfolder.watch_title"))
        if not d:
            return
        self.ctx.hotfolders.update(folder_id, watch_dir=d)
        self._cards[folder_id].set_watch(d)

    def _pick_out(self, folder_id: str) -> None:
        d = filedialog.askdirectory(parent=self, title=t("hotfolder.out_title"))
        if not d:
            return
        self.ctx.hotfolders.update(folder_id, output_dir=d)
        self._cards[folder_id].set_out(d)

    def _add_folder(self) -> None:
        d = filedialog.askdirectory(parent=self, title=t("hotfolder.watch_title"))
        if not d:
            return
        base = os.path.basename(d.rstrip("/\\")) or t("hotfolder.default_name")
        taken = {e["name"] for e in self.ctx.hotfolders.entries()}
        name, n = base, 2
        while name in taken:
            name = f"{base} {n}"
            n += 1
        fid = self.ctx.hotfolders.add({
            "name": name, "watch_dir": d, "output_dir": "", "preset": "bw",
            "convert_existing": False, "enabled": False,
        })
        self._sync_cards()
        self.ctx.status.set_status(
            t("hotfolder.added", name=name), "idle")

    def _delete_folder(self, folder_id: str, btn) -> None:
        # Armement en deux clics, pas de modale imbriquée (idiome « Gérer
        # les presets »).
        if folder_id not in self._confirm_delete:
            self._confirm_delete.add(folder_id)
            btn.configure(text=t("common.confirm"), text_color=pair("error"))
            return
        self._confirm_delete.discard(folder_id)
        entry = self.ctx.hotfolders.entry(folder_id)
        self.ctx.hotfolders.remove(folder_id)
        self._sync_cards()
        if entry is not None:
            self.ctx.status.set_status(
                t("hotfolder.deleted", name=entry["name"]), "idle")

    def _commit_rename(self, folder_id: str, new: str) -> None:
        self.ctx.hotfolders.update(folder_id, name=new)
        card = self._cards.get(folder_id)
        if card is not None:
            card.set_name(new)

    # ── Événements du manager (threads watcher/worker → GUI) ─────────────
    def _queue_event(self, event: dict) -> None:
        try:
            self.after(0, lambda: self._apply_event(event))
        except RuntimeError:
            pass  # application fermée pendant la surveillance

    def _apply_event(self, event: dict) -> None:
        if not self.winfo_exists():
            return
        if event["kind"] == "state":
            card = self._cards.get(event["id"])
            if card is not None:
                card.set_running(event["running"])
            return
        if event["kind"] == "history":
            self._refresh_history()
            return
        entry = self.ctx.hotfolders.entry(event["id"])
        name = entry["name"] if entry else "?"
        self._log_line(f"[{name}] {event['text']}")

    def _log_line(self, message: str) -> None:
        if not self.winfo_exists():
            return
        self._log.configure(state="normal")
        self._log.insert("end", f"{message}\n")
        if int(self._log.index("end-1c").split(".")[0]) > 200:
            self._log.delete("1.0", "2.0")
        self._log.see("end")
        self._log.configure(state="disabled")

    # ── Historique (onglet de droite) ─────────────────────────────────────
    def _history(self):
        manager = self.ctx.hotfolders
        return getattr(manager, "history", None) if manager is not None else None

    def _on_tab(self, value: str) -> None:
        journal = value == t("history.tab")
        (self._page_log.grid if journal else self._page_log.grid_remove)()
        (self._page_hist.grid_remove if journal else self._page_hist.grid)()
        (self._caption.grid if journal else self._caption.grid_remove)()
        (self._clear_btn.grid_remove if journal else self._clear_btn.grid)()
        self._disarm_clear()
        if not journal:
            self._refresh_history()

    def _clear_history(self) -> None:
        # Deux clics, comme la suppression de dossier.
        if not self._clear_armed:
            self._clear_armed = True
            self._clear_btn.configure(text=t("common.confirm"),
                                      text_color=pair("error"))
            return
        self._disarm_clear()
        history = self._history()
        if history is not None:
            history.clear()
        self._refresh_history()

    def _disarm_clear(self) -> None:
        self._clear_armed = False
        self._clear_btn.configure(text=t("history.clear"),
                                  text_color=pair("muted"))

    def _refresh_history(self) -> None:
        if not self.winfo_exists():
            return
        for child in self._hist.winfo_children():
            child.destroy()
        history = self._history()
        entries = history.entries() if history is not None else []
        if not entries:
            ctk.CTkLabel(self._hist, justify="center",
                         text_color=pair("faint"),
                         text=t("history.empty")).pack(pady=28, fill="x")
            return
        for entry in entries[:150]:
            self._history_row(entry)

    def _history_row(self, entry: dict) -> None:
        row = ctk.CTkFrame(self._hist, fg_color="transparent")
        row.pack(fill="x", pady=1)
        row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row, text=self._fmt_ts(entry.get("ts", "")),
                     width=118, anchor="w", text_color=pair("muted"),
                     font=ctk.CTkFont(size=10)).grid(
            row=0, column=0, sticky="w")
        title = (f"{entry.get('folder_name', '?')}"
                 f" · {os.path.basename(entry.get('input', ''))}"
                 f" → {os.path.basename(entry.get('output', ''))}")
        ctk.CTkLabel(row, text=title, anchor="w",
                     font=ctk.CTkFont(size=11)).grid(
            row=0, column=1, sticky="ew")
        status = entry.get("status", "")
        keys = {"done": "history.status_done", "error": "history.status_error",
                "cancelled": "history.status_cancelled",
                "pending": "history.status_pending"}
        colors = {"done": pair("success"), "error": pair("error"),
                  "cancelled": pair("faint"), "pending": pair("muted")}
        ctk.CTkLabel(row, anchor="e", text_color=colors.get(status,
                                                            pair("muted")),
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text=t(keys[status]) if status in keys
                     else status).grid(
            row=0, column=2, sticky="e", padx=(8, 0))

    @staticmethod
    def _fmt_ts(ts: str) -> str:
        try:
            return datetime.fromisoformat(ts).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return ts

    # ── Démarrage automatique ─────────────────────────────────────────────
    def _on_autostart(self) -> None:
        enabled = bool(self._auto_switch.get())
        minimized = bool(self.ctx.config.get("startup", "start_minimized",
                                             False))
        if not autostart.set_autostart(enabled, minimized):
            self._auto_switch.deselect()
            self._min_switch.deselect()
            self._min_switch.configure(state="disabled")
            self.ctx.status.set_status(
                t("hotfolder.autostart_failed"), "error")
            return
        self.ctx.config.set("startup", "autostart", enabled)
        self._min_switch.configure(
            state="normal" if enabled else "disabled")
        if not enabled:
            self._min_switch.deselect()
        self.ctx.status.set_status(
            t("hotfolder.autostart_on") if enabled
            else t("hotfolder.autostart_off"), "ok")

    def _on_start_minimized(self) -> None:
        minimized = bool(self._min_switch.get())
        self.ctx.config.set("startup", "start_minimized", minimized)
        # Réécrit l'artefact avec/sans --minimized (l'option est portée par
        # la commande, pas par la config).
        if not autostart.set_autostart(True, minimized):
            self.ctx.status.set_status(
                t("hotfolder.autostart_update_failed"), "error")

    # ── Divers ────────────────────────────────────────────────────────────
    def apply_theme(self, tokens: dict) -> None:
        super().apply_theme(tokens)
        self._list.configure(fg_color=pair("surface"))
        self._log.configure(fg_color=pair("bg"), text_color=pair("muted"))
        self._hist.configure(fg_color=pair("bg"))
        self._refresh_history()  # lignes reconstruites aux couleurs du thème
        for card in self._cards.values():
            card.restyle()


class _FolderCard(Card):
    """Une carte par dossier surveillé — widgets muets : chaque action
    délègue à la vue avec l'id du dossier."""

    def __init__(self, master, view: HotFolderView, entry: dict):
        super().__init__(master)
        self._view = view
        self.folder_id = entry["id"]
        self._name = entry.get("name", "")
        self._watch_dir = entry.get("watch_dir", "")
        self._out_dir = entry.get("output_dir", "")
        self.is_running = False

        self.grid_columnconfigure(1, weight=1)

        # Interrupteur + état + actions.
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=3, sticky="ew", padx=14,
                  pady=(12, 0))
        self.toggle = ctk.CTkSwitch(
            head, text=t("hotfolder.watching"),
            progress_color=pair("primary"),
            command=lambda: view._on_toggle(self.folder_id))
        self.toggle.pack(side="left")
        self.state_lbl = ctk.CTkLabel(head, text=t("hotfolder.inactive"),
                                      text_color=pair("muted"),
                                      font=ctk.CTkFont(size=11))
        self.state_lbl.pack(side="left", padx=(12, 0))
        self._del_btn = GhostButton(
            head, text=t("common.delete"), width=86, height=26,
            command=lambda: view._delete_folder(self.folder_id,
                                                self._del_btn))
        self._del_btn.pack(side="right")
        self._ren_btn = GhostButton(head, text=t("common.rename"), width=86,
                                    height=26, command=self.begin_rename)
        self._ren_btn.pack(side="right", padx=(0, 6))

        # Nom (libellé ↔ saisie de renommage sur la même rangée).
        self._name_lbl = ctk.CTkLabel(self, text=self._name, anchor="w",
                                      font=ctk.CTkFont(size=13,
                                                       weight="bold"))
        self._name_lbl.grid(row=1, column=0, columnspan=3, sticky="w",
                            padx=14, pady=(4, 0))
        self._name_entry = ctk.CTkEntry(self, height=28)
        self._name_ok = GhostButton(self, text=t("common.validate"), width=72,
                                    height=28, state="disabled",
                                    command=self._commit_name)
        self._name_cancel = GhostButton(self, text=t("common.cancel"),
                                        width=72, height=28,
                                        command=self._cancel_rename)
        self._name_entry.bind("<Return>",
                              lambda _e: self._commit_name())
        self._name_entry.bind("<Escape>", lambda _e: self._cancel_rename())
        self._name_entry.bind("<KeyRelease>", lambda _e: self._check_name())

        self._watch_entry = self._dir_row(
            2, t("hotfolder.watch_dir"), self._watch_dir,
            lambda: view._pick_watch(self.folder_id))
        self._out_entry = self._dir_row(
            3, t("hotfolder.out_dir"), self._out_dir,
            lambda: view._pick_out(self.folder_id))
        ctk.CTkLabel(self, anchor="w", text_color=pair("faint"),
                     font=ctk.CTkFont(size=10),
                     text=t("hotfolder.out_hint")
                     ).grid(row=4, column=1, columnspan=2, sticky="w",
                            padx=(0, 14))

        row_preset = ctk.CTkFrame(self, fg_color="transparent")
        row_preset.grid(row=5, column=0, columnspan=3, sticky="ew", padx=14,
                        pady=(4, 12))
        ctk.CTkLabel(row_preset, text=t("hotfolder.preset_label"),
                     text_color=pair("muted"),
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 10))
        # Preset relu à CHAQUE fichier arrivant : changer de puce pendant la
        # surveillance s'applique au fichier suivant, sans redémarrage.
        self.picker = PresetPicker(
            row_preset, on_select=lambda label: view._on_preset(
                self.folder_id, label))
        self.picker.pack(side="left")

    def _dir_row(self, row: int, label: str, value: str, command):
        ctk.CTkLabel(self, text=label, anchor="w", text_color=pair("muted"),
                     font=ctk.CTkFont(size=11)).grid(
            row=row, column=0, sticky="w", padx=(14, 8), pady=(6, 0))
        entry = ctk.CTkEntry(self, height=30, state="disabled")
        entry.grid(row=row, column=1, sticky="ew", padx=(0, 0), pady=(6, 0))
        GhostButton(self, text=t("common.browse"), width=92, height=30,
                    command=command).grid(row=row, column=2, padx=(8, 14),
                                          pady=(6, 0))
        self._fill(entry, value)
        return entry

    @staticmethod
    def _fill(entry, value: str) -> None:
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, value)
        entry.configure(state="disabled")

    # ── État piloté par la vue ────────────────────────────────────────────
    def set_running(self, running: bool) -> None:
        self.is_running = running
        (self.toggle.select if running else self.toggle.deselect)()
        if running:
            leaf = os.path.basename(self._watch_dir.rstrip("/\\")) or self._name
            self.state_lbl.configure(text=t("hotfolder.active_leaf", leaf=leaf),
                                     text_color=pair("success"))
        else:
            self.state_lbl.configure(text=t("hotfolder.inactive"),
                                     text_color=pair("muted"))

    def set_watch(self, path: str) -> None:
        self._watch_dir = path
        self._fill(self._watch_entry, path)
        self.set_running(self.is_running)  # l'état « Actif — … » suit

    def set_out(self, path: str) -> None:
        self._out_dir = path
        self._fill(self._out_entry, path)

    def set_name(self, name: str) -> None:
        self._name = name
        self._name_lbl.configure(text=name)

    def refresh_picker(self, active_display: str | None) -> None:
        presets = self._view.ctx.presets
        self.picker.set_options(
            [presets.display_name(k) for k in presets.keys()],
            active=active_display)

    def restyle(self) -> None:
        # Bascule de thème : les paires [light, dark] restent vivantes, seuls
        # les textes d'état doivent être re-résolus selon l'état courant.
        self.set_running(self.is_running)

    # ── Renommage en ligne (idiome « Gérer les presets ») ─────────────────
    def begin_rename(self) -> None:
        self._name_lbl.grid_remove()
        self._name_entry.grid(row=1, column=0, sticky="ew", padx=14,
                              pady=(4, 0))
        self._name_ok.grid(row=1, column=1, sticky="e", pady=(4, 0))
        self._name_cancel.grid(row=1, column=2, sticky="e", padx=(0, 14),
                               pady=(4, 0))
        self._name_entry.delete(0, "end")
        self._name_entry.insert(0, self._name)
        self._name_entry.focus_set()
        self._name_entry.icursor("end")
        self._check_name()

    def _check_name(self) -> bool:
        ok = bool(self._name_entry.get().strip())
        self._name_ok.configure(state="normal" if ok else "disabled")
        return ok

    def _commit_name(self) -> None:
        new = self._name_entry.get().strip()
        if new:
            self._view._commit_rename(self.folder_id, new)
        self._cancel_rename()

    def _cancel_rename(self) -> None:
        self._name_entry.grid_remove()
        self._name_ok.grid_remove()
        self._name_cancel.grid_remove()
        self._name_lbl.grid()
