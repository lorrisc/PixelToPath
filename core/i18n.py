"""Support i18n minimal — un JSON par langue, sans dépendance GUI.

Le français (locales/fr.json) est la langue source : clés = slugs
pointés anglais (ex. « nav.convert »), valeurs françaises. Un autre
langage se traduit en copiant fr.json et en traduisant les valeurs ;
les clés manquantes retombent sur le français, puis sur la clé elle-même.

Règles de format :
- toute valeur passe par str.format(**kwargs) — les accolades littérales
  d'une traduction doivent donc être doublées (« {{ » / « }} ») ;
- le pluriel (tp) attend un dict {"one": …, "other": …} ; règle
  française n <= 1 → « one » (0 fichier, 1 fichier) — à étendre par
  langue quand d'autres locales verront des règles différentes ;
- le bloc spécial « _meta » ({"name": "Français"}, nom natif affiché
  dans le sélecteur) est ignoré par la recherche.

Vie dans les threads : load_language échange une référence de dict
(atomique en CPython) — t() est appelé depuis les threads watcher et
worker (journaux hot folder) sans verrou.
"""

import json
import os
import sys
from pathlib import Path

DEFAULT_LANGUAGE = "en"

# _LANGS : cache des dictionnaires aplatis par code ; _lang : code actif.
_LANGS: dict[str, dict] = {}
_lang: str = ""
_warned: set[str] = set()


def _resource_path(relative_path: str) -> str:
    """Miroir de interface/utils.resource_path — core n'importe jamais
    interface/, donc le contournement PyInstaller est dupliqué ici."""
    if getattr(sys, "frozen", False):  # PyInstaller
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def _flatten(data, prefix: str = "") -> dict:
    """{"nav": {"convert": "…"}} → {"nav.convert": "…"} (bloc _meta exclu)."""
    flat: dict[str, str | dict] = {}
    for key, value in (data or {}).items():
        if key.startswith("_"):
            continue
        full = f"{prefix}{key}"
        if isinstance(value, dict):
            if "one" in value or "other" in value:
                flat[full] = value  # dict de pluriel, pas un sous-arbre
            else:
                flat.update(_flatten(value, prefix=f"{full}."))
        else:
            flat[full] = str(value)
    return flat


def _read_flat(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return _flatten(data)


def _locales_dir() -> Path:
    return Path(_resource_path("locales"))


def load_language(code: str, locales_dir: str | None = None) -> bool:
    """Charge <code>.json et en fait la langue active. False si absent."""
    directory = Path(locales_dir) if locales_dir else _locales_dir()
    data = _read_flat(directory / f"{code}.json")
    if not data:
        return False
    global _lang
    _LANGS[code] = data
    # Le repli (anglais) vient du MÊME répertoire que la langue chargée :
    # une locale testée en dehors de locales/ reste auto-cohérente.
    if code != DEFAULT_LANGUAGE and DEFAULT_LANGUAGE not in _LANGS:
        _LANGS[DEFAULT_LANGUAGE] = _read_flat(
            directory / f"{DEFAULT_LANGUAGE}.json")
    _lang = code
    return True


def install_from_config(config) -> str:
    """Lit general.language, charge la langue, renvoie le code effectif.

    Un code inconnu (ou un fichier manquant) retombe sur l'anglais.
    """
    code = str(config.get("general", "language", DEFAULT_LANGUAGE)
               or DEFAULT_LANGUAGE)
    if not load_language(code):
        load_language(DEFAULT_LANGUAGE)
    return current_language()


def current_language() -> str:
    return _lang or DEFAULT_LANGUAGE


def available_languages() -> list[dict]:
    """Langues installées [{"code", "name"}] — langue par défaut (en)
    d'abord, puis tri alphabétique des noms natifs (_meta.name, défaut :
    code)."""
    names: dict[str, str] = {}
    for path in sorted(_locales_dir().glob("*.json")):
        meta = {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(raw, dict) and isinstance(raw.get("_meta"), dict):
            meta = raw["_meta"]
        names[path.stem] = str(meta.get("name") or path.stem)
    ordered = [DEFAULT_LANGUAGE] if DEFAULT_LANGUAGE in names else []
    ordered += sorted(c for c in names if c != DEFAULT_LANGUAGE)
    return [{"code": code, "name": names[code]} for code in ordered]


def key_values(key: str) -> dict[str, str]:
    """Valeur de `key` dans CHAQUE langue disponible : {code: valeur}.

    Sert à réserver un libellé traduit (noms de presets interdits) dans
    toutes les langues, pas seulement la langue courante.
    """
    values: dict[str, str] = {}
    for path in sorted(_locales_dir().glob("*.json")):
        flat = _LANGS.get(path.stem) or _read_flat(path)
        value = flat.get(key)
        if isinstance(value, str) and value:
            values[path.stem] = value
    return values


# ── Recherche ────────────────────────────────────────────────────────────────
def _lookup(key: str) -> str:
    if DEFAULT_LANGUAGE not in _LANGS:
        # Auto-init : t() doit fonctionner même sans install_from_config
        # (tests, modules core utilisés hors app).
        _LANGS[DEFAULT_LANGUAGE] = _read_flat(
            _locales_dir() / f"{DEFAULT_LANGUAGE}.json")
    lang = _LANGS.get(_lang)
    if lang is not None and key in lang:
        return lang[key]
    fallback = _LANGS.get(DEFAULT_LANGUAGE)
    if fallback is not None and key in fallback:
        return fallback[key]
    if key not in _warned:
        _warned.add(key)
        print(f"[i18n] clé absente : {key}", file=sys.stderr)
    return key


def _format(value, kwargs: dict) -> str:
    # Un dict de pluriel demandé via t() : forme « other » par défaut.
    if isinstance(value, dict):
        value = str(value.get("other") or value.get("one") or "")
    # Une clé appelée sans ses placeholders (ou une traduction incomplète)
    # ne doit jamais lever : on rend la valeur brute.
    try:
        return value.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return value


def t(_key: str, /, **kwargs) -> str:
    """Traduit la clé (repli langue par défaut → clé) et applique
    str.format(**kwargs).

    Paramètre positionnel seul : un placeholder peut s'appeler `key`
    (ex. « preset « {key} » introuvable ») sans collision.
    """
    return _format(_lookup(_key), kwargs)


def tp(_key: str, _n: int, /, **kwargs) -> str:
    """Variante plurielle : {"one": …, "other": …}, règle française
    n <= 1 → « one ». `n` est injecté automatiquement."""
    value = _lookup(_key)
    if isinstance(value, dict):
        lang = current_language()
        if lang == "ru":
            is_one = _n % 10 == 1 and _n % 100 != 11
        elif lang in ("fr", "pt_BR", "hi"):
            is_one = _n <= 1
        else:
            # Default to n == 1 for English, Spanish, German, Arabic, etc.
            is_one = _n == 1
        value = str(value.get("one" if is_one else "other")
                    or value.get("other") or value.get("one") or "")
    kwargs.setdefault("n", _n)
    return _format(value, kwargs)
