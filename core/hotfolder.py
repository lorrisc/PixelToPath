"""Hot folder — surveillance d'un dossier, SVG automatiques, sans GUI.

Boucle daemon (polling 2 s, pas d'inotify : fiable sur les montages
réseau) ; un fichier n'est soumis que lorsqu'il est stable — même
(mtime, taille) sur deux scans consécutifs — pour ne pas convertir une
copie à moitié écrite. Une sortie plus récente que son entrée est
ignorée : redémarrer la surveillance ne reconvertit pas l'historique.

Le watcher ne convertit pas lui-même : il émet `on_ready(entrée, sortie)`
— la vue le branche sur le ConversionWorker, la CLI sur convert_file.
"""

import os
import threading
from collections import deque

from core.constants import IMG_EXTS
from core.i18n import t, tp


class HotFolderWatcher:
    POLL_S = 2.0
    STABLE_AFTER = 2  # scans identiques consécutifs requis

    def __init__(self, on_ready, on_message=lambda msg: None):
        self._on_ready = on_ready
        self._on_message = on_message
        self.messages: deque[str] = deque(maxlen=200)
        self._pending: dict[str, dict] = {}  # chemin → stat + compteur stable
        self._done: dict[str, tuple] = {}    # chemin → stat au moment de l'envoi
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._watch_dir = ""
        self._output_dir = ""

    # ── Cycle de vie ──────────────────────────────────────────────────────
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, watch_dir: str, output_dir: str,
              convert_existing: bool = False) -> None:
        if self.running():
            return
        self._watch_dir = watch_dir
        self._output_dir = output_dir or watch_dir
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="ptp-hotfolder")
        self._thread.start()
        self._say(t("hotfolder.msg.watching", dir=watch_dir))
        if convert_existing:
            converted = self._submit_existing()
            self._say(tp("hotfolder.msg.existing", converted))

    def stop(self) -> None:
        self._stop.set()
        self._thread = None
        self._say(t("hotfolder.msg.stopped"))

    # ── Boucle ────────────────────────────────────────────────────────────
    def _loop(self) -> None:
        while not self._stop.wait(self.POLL_S):
            try:
                self._scan()
            except OSError:
                continue  # dossier momentanément indisponible (clé USB…)

    def _scan(self) -> None:
        seen = set()
        for entry in os.scandir(self._watch_dir):
            if not entry.is_file():
                continue
            if os.path.splitext(entry.name)[1].lower() not in IMG_EXTS:
                continue
            path = entry.path
            seen.add(path)
            try:
                stat = (entry.stat().st_mtime, entry.stat().st_size)
            except OSError:
                continue  # le fichier vient de disparaître

            if self._done.get(path) == stat:
                continue  # déjà envoyé, inchangé depuis
            self._done.pop(path, None)

            info = self._pending.get(path)
            if info is not None and info["stat"] == stat:
                info["stable"] += 1
            else:
                # Premier scan ou fichier réécrit entre deux tours.
                self._pending[path] = {"stat": stat, "stable": 1}
                continue
            if info["stable"] < self.STABLE_AFTER:
                continue

            # Stable : sortie prévue plus récente → simple reprise.
            out = self._output_for(path, stat)
            self._pending.pop(path, None)
            self._done[path] = stat
            if out is not None:
                self._say(t("hotfolder.msg.converting",
                            name=os.path.basename(path)))
                self._on_ready(path, out)

        # Fichiers disparus : on oublie (relimitation mémoire).
        for cache in (self._pending, self._done):
            for path in [p for p in cache if p not in seen]:
                del cache[path]

    def _submit_existing(self) -> int:
        """convert_existing : envoie tout ce qui traîne au démarrage."""
        count = 0
        for entry in os.scandir(self._watch_dir):
            if not entry.is_file():
                continue
            if os.path.splitext(entry.name)[1].lower() not in IMG_EXTS:
                continue
            try:
                stat = (entry.stat().st_mtime, entry.stat().st_size)
            except OSError:
                continue
            out = self._output_for(entry.path, stat)
            if out is None:
                continue
            self._done[entry.path] = stat
            count += 1
            self._say(t("hotfolder.msg.converting", name=entry.name))
            self._on_ready(entry.path, out)
        return count

    # ── Sorties ───────────────────────────────────────────────────────────
    def _output_for(self, path: str, stat: tuple) -> str | None:
        """Chemin de sortie, ou None si le SVG est déjà plus récent."""
        stem = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(self._output_dir, f"{stem}.svg")
        try:
            if os.path.exists(out) and os.stat(out).st_mtime >= stat[0]:
                return None
        except OSError:
            return None
        return out

    def _say(self, message: str) -> None:
        self.messages.append(message)
        self._on_message(message)
