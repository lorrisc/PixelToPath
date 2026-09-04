"""Gestionnaire des hot folders — N dossiers surveillés, sans GUI.

Un HotFolderWatcher (core/hotfolder.py) par entrée de la section
« hotfolders » de la config, qui reste la source unique de vérité. Le
manager vit au niveau de l'application (créé par app.main) : la
surveillance démarre au lancement, sans aucune vue construite, et
survit au masquage de la fenêtre. La vue Hot folder ne fait
qu'orchestrer — elle s'abonne aux événements (émis depuis les threads
watcher) et rejoue les journaux, conservés dans le deque de chaque
watcher, à sa construction.

La résolution du preset a lieu À L'ARRIVÉE du fichier, pas au démarrage
: changer de preset (ou ses réglages) pendant une surveillance active
s'applique au fichier suivant sans redémarrage.
"""

import itertools
import os

from core.config import new_hotfolder_id
from core.convert_service import ConversionWorker
from core.hotfolder import HotFolderWatcher
from core.history import HotFolderHistory
from core.i18n import t

# Clés dont la modification à chaud exige un redémarrage du watcher.
_RESTART_KEYS = ("watch_dir", "output_dir", "convert_existing")


class HotFolderManager:
    def __init__(self, config, presets, worker_factory=None,
                 history: HotFolderHistory | None = None):
        self._config = config
        self._presets = presets
        # Injecté par app.py : le worker partagé (ctx.worker) doit être
        # créé une seule fois et porter le listener de notifications.
        # Défaut : un ConversionWorker neuf (CLI, tests).
        self._worker_factory = worker_factory or ConversionWorker
        # Historique persistant : None dans les tests qui ne le déclarent
        # pas — aucune écriture de fichier implicite hors de l'app.
        self.history = history
        self._worker = None
        self._watchers: dict[str, HotFolderWatcher] = {}
        self._ids = itertools.count(1)
        self._listeners: list = []

    # ── Entrées (lecture/écriture de la config) ───────────────────────────
    def entries(self) -> list[dict]:
        # get(section) sans clé renvoie la section entière ({} si absente).
        return [dict(e) for e in self._config.get("hotfolders") or []]

    def entry(self, folder_id: str) -> dict | None:
        for entry in self.entries():
            if entry["id"] == folder_id:
                return entry
        return None

    def add(self, entry: dict) -> str:
        entry = dict(entry)
        entry["id"] = new_hotfolder_id()
        entries = self.entries()
        entries.append(entry)
        self._config.set("hotfolders", None, entries)
        return entry["id"]

    def update(self, folder_id: str, **changes) -> bool:
        entries = self.entries()
        for entry in entries:
            if entry["id"] != folder_id:
                continue
            watcher = self._watchers.get(folder_id)
            restart = bool(
                watcher is not None and watcher.running()
                and any(key in changes and entry.get(key) != changes[key]
                        for key in _RESTART_KEYS))
            entry.update(changes)
            self._config.set("hotfolders", None, entries)
            if restart:  # changement à chaud : on repart propre
                watcher.stop()
                self._launch_watcher(entry)
            return True
        return False

    def remove(self, folder_id: str) -> None:
        watcher = self._watchers.pop(folder_id, None)
        if watcher is not None:
            watcher.stop()
        entries = [e for e in self.entries() if e["id"] != folder_id]
        self._config.set("hotfolders", None, entries)

    # ── Cycle de vie ──────────────────────────────────────────────────────
    def start(self, folder_id: str) -> bool:
        entry = self.entry(folder_id)
        if entry is None:
            return False
        watch_dir = entry.get("watch_dir", "")
        if not watch_dir or not os.path.isdir(watch_dir):
            self._say(folder_id, t("hotfolder.msg.folder_missing",
                                   dir=watch_dir or t("hotfolder.msg.no_dir")))
            return False
        # Worker partagé avec le batch : réarmer l'annulation ICI (début de
        # session de surveillance), pas à chaque fichier.
        self._ensure_worker().resume()
        self._launch_watcher(entry)
        self._set_enabled(folder_id, True)
        self._emit_state(folder_id, True)
        return True

    def stop(self, folder_id: str, persist: bool = True) -> None:
        watcher = self._watchers.get(folder_id)
        if watcher is not None:
            watcher.stop()
        if persist:
            self._set_enabled(folder_id, False)
        self._emit_state(folder_id, False)

    def start_all(self) -> int:
        """Démarre toute entrée enabled (au lancement, reprise de licence)."""
        count = 0
        for entry in self.entries():
            if entry.get("enabled") and self.start(entry["id"]):
                count += 1
        return count

    def stop_all(self, persist: bool = True) -> None:
        # persist=False (perte de licence, fermeture) : enabled intacts,
        # la surveillance reprendra à la réactivation / au prochain lancement.
        for folder_id in list(self._watchers):
            self.stop(folder_id, persist=persist)

    def running_ids(self) -> list[str]:
        return [fid for fid, w in self._watchers.items() if w.running()]

    def any_running(self) -> bool:
        """Décide du sort du bouton Fermer : masquer au tray ou quitter."""
        return any(w.running() for w in self._watchers.values())

    def journal(self, folder_id: str) -> list[str]:
        """Lignes conservées par le watcher — rejouées quand la vue Hot
        folder est (re)construite, même sans vue au moment des faits."""
        watcher = self._watchers.get(folder_id)
        return list(watcher.messages) if watcher is not None else []

    def _launch_watcher(self, entry: dict) -> None:
        folder_id = entry["id"]
        watcher = self._watchers.get(folder_id)
        if watcher is None:
            watcher = HotFolderWatcher(
                on_ready=lambda path, out, fid=folder_id: self._on_ready(fid, path, out),
                on_message=lambda msg, fid=folder_id: self._say(fid, msg))
            self._watchers[folder_id] = watcher
        # start() sur un watcher déjà vivant est un no-op ; le redémarrage
        # à chaud passe donc toujours par stop() d'abord (update()).
        watcher.start(entry.get("watch_dir", ""), entry.get("output_dir") or "",
                      convert_existing=bool(entry.get("convert_existing")))

    def _set_enabled(self, folder_id: str, enabled: bool) -> None:
        entries = self.entries()
        for entry in entries:
            if entry["id"] == folder_id:
                if entry.get("enabled") != enabled:
                    entry["enabled"] = enabled
                    self._config.set("hotfolders", None, entries)
                return

    # ── Conversions ───────────────────────────────────────────────────────
    def _on_ready(self, folder_id: str, input_path: str,
                  output_path: str) -> None:
        entry = self.entry(folder_id)
        key = (entry or {}).get("preset", "bw")
        params = self._presets.params(key)
        if params is None:
            # Preset (personnalisé) supprimé depuis : produire quand même
            # une sortie — en arrière-plan un skip silencieux se perd.
            # Repli sur « bw », le même que celui affiché par la vue.
            fallback = self._presets.display_name("bw")
            self._say(folder_id, t("hotfolder.msg.preset_fallback", key=key,
                                   fallback=fallback))
            params = self._presets.params("bw")
        if params is None:
            return  # même les intégrés absentes : impossible en pratique
        item_id = ("hotfolder", folder_id, next(self._ids))
        if self.history is not None:
            self.history.record(item_id, folder_id,
                                (entry or {}).get("name", ""),
                                input_path, output_path)
        self._ensure_worker().submit(
            item_id, input_path, output_path, params)

    def _ensure_worker(self):
        if self._worker is None:
            self._worker = self._worker_factory()
            # Les lignes de résultat existent même sans vue (replay à la
            # construction de la vue) ; les ids « batch » sont ignorés.
            self._worker.add_listener(self._on_worker_result)
        return self._worker

    def _on_worker_result(self, item_id, status: str, detail: str) -> None:
        # Thread worker. Convention de préfixe : ("hotfolder", folder_id, n).
        if not (isinstance(item_id, tuple) and len(item_id) > 1
                and item_id[0] == "hotfolder"):
            return
        folder_id = item_id[1]
        if self.history is not None:
            self.history.settle(item_id, status)
            self._emit({"kind": "history", "id": folder_id})
        if status == "done":
            self._say(folder_id, t("hotfolder.msg.done",
                                   name=os.path.basename(detail)))
        elif status == "error":
            self._say(folder_id, t("hotfolder.msg.error", detail=detail))

    # ── Observateurs (callbacks sur threads watcher/worker) ──────────────
    def add_listener(self, listener) -> None:
        """`listener(event)` — event = {"kind": "message"|"state", "id": …}."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener) -> None:
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    def _say(self, folder_id: str, message: str) -> None:
        # Le deque du watcher est déjà rempli par HotFolderWatcher._say ;
        # ici on ne fait que propager aux observateurs (la vue y abonne
        # son journal — sans ré-empiler, sinon la ligne serait doublée).
        self._emit({"kind": "message", "id": folder_id, "text": message})

    def _emit_state(self, folder_id: str, running: bool) -> None:
        self._emit({"kind": "state", "id": folder_id, "running": running})

    def _emit(self, event: dict) -> None:
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception as exc:  # un listener fautif ne tue pas la boucle
                print(f"Listener hot folder : {exc}")
