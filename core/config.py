"""Configuration utilisateur persistante (JSON atomique, sans dépendance GUI)."""

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

SCHEMA_VERSION = 2

# Valeurs par défaut — toute section manquante dans config.json est recréée.
# La section v1 « hotfolder » (un seul dossier surveillé) a disparu au
# profit de « hotfolders » (liste) : le fichier v1 est migré dans _load().
_DEFAULTS = {
    "schema_version": SCHEMA_VERSION,
    "appearance": {"mode": "light"},
    "general": {"language": "en"},
    "convert": {"active_preset": "bw", "last_params": {}},
    "custom_presets": {},   # nom → kwargs vtracer (dict : ordre d'insertion)
    "pro": {
        "license_key": "",
        "instance_id": "",
        "activated_at": "",
        "last_validated_at": "",
    },
    "hotfolders": [],       # dossiers surveillés, ordre = ordre d'affichage
    "startup": {
        "autostart": False,
        "start_minimized": False,
    },
    "batch": {"last_output_dir": ""},
}


def new_hotfolder_id() -> str:
    return f"hf-{uuid.uuid4().hex[:8]}"


def migrate_v1_to_v2(data: dict) -> bool:
    """Hotfolder plat (v1) → liste « hotfolders » (v2). True si modifié.

    Pure : opère sur le dict passé, sans toucher au disque — testable
    telle quelle. Les cinq champs de l'ancienne section sont copiés tels
    quels dans une entrée unique ; un hotfolder vide ou absent donne une
    liste vide. Idempotent : un fichier déjà v2 n'est pas réécrit.
    """
    try:
        version = int(data.get("schema_version", 1))
    except (TypeError, ValueError):
        version = 1
    if version >= 2:
        return False

    old = data.pop("hotfolder", None)
    if isinstance(old, dict) and old.get("watch_dir"):
        base = os.path.basename(str(old["watch_dir"]).rstrip("/\\"))
        data["hotfolders"] = [{
            "id": new_hotfolder_id(),
            "name": base or "Dossier 1",
            "watch_dir": old.get("watch_dir", ""),
            "output_dir": old.get("output_dir", ""),
            "preset": old.get("preset", "bw"),
            "convert_existing": bool(old.get("convert_existing", False)),
            "enabled": bool(old.get("enabled", False)),
        }]
    else:
        data["hotfolders"] = []
    data.setdefault("startup", dict(_DEFAULTS["startup"]))
    data["schema_version"] = 2
    return True


def user_config_dir() -> Path:
    """Répertoire de configuration selon l'OS."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(base) / "PixelToPath"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PixelToPath"
    base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(base) / "PixelToPath"


class ConfigStore:
    """Dictionnaire persisté dans config.json, écriture atomique (.tmp + replace).

    Un seul ConfigStore par application ; muté sur le thread GUI uniquement.
    """

    def __init__(self, path: Path | None = None):
        # `path` : injectable pour les tests (défaut = config utilisateur).
        self.path = path or user_config_dir() / "config.json"
        self._data = json.loads(json.dumps(_DEFAULTS))  # copie profonde
        self._load()

    def _load(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        # Fusion : les clés par défaut absentes du fichier restent disponibles.
        for section, values in raw.items():
            if isinstance(values, dict) and isinstance(self._data.get(section), dict):
                self._data[section].update(values)
            else:
                self._data[section] = values
        # Migration v1 → v2 (hotfolder plat → hotfolders[]) : réécrite une
        # seule fois, les lancements suivants repartent d'un fichier v2.
        if migrate_v1_to_v2(self._data):
            self.save()

    def get(self, section: str, key: str | None = None, default=None):
        sec = self._data.get(section, {})
        if key is None:
            return sec
        return sec.get(key, default)

    def set(self, section: str, key: str | None, value) -> None:
        # key=None : remplacer la section entière (listes/dicts reconstruits).
        if key is None:
            self._data[section] = value
        else:
            self._data.setdefault(section, {})[key] = value
        self.save()

    def remove(self, section: str, key: str) -> None:
        self._data.get(section, {}).pop(key, None)
        self.save()

    def save(self) -> None:
        """Écriture atomique pour ne jamais corrompre la config."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=self.path.parent, prefix=".config-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
