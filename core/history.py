"""Historique persistant des conversions hot folder — JSON dédié, sans GUI.

Pourquoi pas ConfigStore : record() est appelé depuis le thread watcher
et settle() depuis le thread worker, alors que ConfigStore est documenté
« GUI thread only ». Ce store porte son propre verrou et réécrit le
fichier de façon atomique à chaque mutation ; les lectures (vue) passent
par le même verrou, les listes rendues sont des copies.

Le fichier vit à côté de la config : user_config_dir()/history.json.
Chaque entrée : {"ts", "folder_id", "folder_name", "input", "output",
"status"} — ts ISO à la seconde (idiome core/licensing.py), status ∈
pending|done|error|cancelled. La corrélation submit → résultat se fait
par item_id (tuple hashable) : `pending` signifie « conversion non
terminée au moment de quitter » — de telles entrées sont supprimées au
chargement, pas affichées comme en cours.
"""

import json
import os
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from core.config import user_config_dir

HISTORY_CAP = 1000  # au-delà : les plus anciennes sont rognées


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class HotFolderHistory:
    def __init__(self, path: Path | None = None, cap: int = HISTORY_CAP):
        # `path` : injectable pour les tests (défaut = à côté de config.json).
        self.path = path or user_config_dir() / "history.json"
        self._cap = cap
        self._lock = threading.Lock()
        self._entries: list[dict] = []          # plus ancienne en tête
        self._pending: dict[tuple, dict] = {}   # item_id → entrée (référence)
        self._load()

    # ── Écriture (threads watcher/worker) ─────────────────────────────────
    def record(self, item_id: tuple, folder_id: str, folder_name: str,
               input_path: str, output_path: str) -> None:
        entry = {
            "ts": _now(),
            "folder_id": folder_id,
            "folder_name": folder_name,
            "input": input_path,
            "output": output_path,
            "status": "pending",
        }
        with self._lock:
            self._entries.append(entry)
            self._pending[item_id] = entry
            del self._entries[:-self._cap]  # rogne les plus anciennes
            self._save()

    def settle(self, item_id: tuple, status: str, detail: str = "") -> None:
        """Résultat worker : done|error|cancelled. `detail` (message
        d'erreur brut) n'est pas persisté — l'entrée garde le statut."""
        with self._lock:
            entry = self._pending.pop(item_id, None)
            if entry is None:
                return  # soumission d'avant le démarrage de l'historique
            entry["status"] = status
            self._save()

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._pending.clear()
            self._save()

    # ── Lecture (thread GUI) ──────────────────────────────────────────────
    def entries(self, limit: int | None = None) -> list[dict]:
        """Copies, plus récentes en tête."""
        with self._lock:
            items = [dict(e) for e in reversed(self._entries)]
        return items if limit is None else items[:limit]

    def for_folder(self, folder_id: str) -> list[dict]:
        return [e for e in self.entries() if e["folder_id"] == folder_id]

    # ── Persistance ───────────────────────────────────────────────────────
    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, list):
            return
        # Une entrée restée « pending » est une transaction incomplète
        # (arrêt pendant la conversion) : elle ne laisse aucune trace.
        self._entries = [e for e in raw
                         if isinstance(e, dict) and e.get("status") != "pending"]
        self._entries = self._entries[-self._cap:]

    def _save(self) -> None:
        """Écriture atomique (idiome ConfigStore). Appelé sous verrou.

        Un échec disque ne doit jamais tuer la surveillance : l'état en
        mémoire reste juste, il sera réécrit à la mutation suivante.
        """
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=self.path.parent, prefix=".history-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._entries, f, indent=2, ensure_ascii=False)
                os.replace(tmp, self.path)
            except OSError:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except OSError as exc:
            print(f"Historique hot folder : {exc}", file=sys.stderr)
