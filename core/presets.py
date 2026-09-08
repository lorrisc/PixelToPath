"""Presets de conversion — intégrés + personnalisés, sans dépendance GUI.

Le format stocké est le kwargs vtracer brut : la même source alimente la
vue de conversion, le batch, le hot folder et la CLI. Les presets
personnalisés vivent dans config.json (section « custom_presets »,
dict nom → params dont l'ordre d'insertion est conservé).

Clé ≠ libellé : la config, la CLI et le hot folder parlent en clés
stables (« bw »), l'interface affiche le libellé traduit
(presets.builtin.bw) résolu à l'appel — jamais figé à l'import.
"""

from moteur.image_utils import PRESETS

from core import i18n
from core.i18n import t

# length_threshold traverse JSON et sliders flottants : comparaison tolérante.
_FLOAT_TOL = 0.01


def reserved_names() -> set[str]:
    """Noms interdits aux presets personnalisés : les clés intégrées ET
    leurs libellés dans TOUTES les langues disponibles (sinon un preset
    « Black & White » personnalisé masquerait l'intégré dans resolve(),
    en anglais). S'y ajoute le libellé de la puce Auto de la vue
    Convertir — un preset personnalisé « Auto » créerait une puce
    dupliquée et une ambiguïté dans resolve()."""
    names = set(PRESETS)
    for key in PRESETS:
        names |= set(i18n.key_values(f"presets.builtin.{key}").values())
    names |= set(i18n.key_values("presets.auto").values())
    return names


def _equal(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        return abs(float(a) - float(b)) <= _FLOAT_TOL
    return a == b


def name_error(name: str, customs) -> str | None:
    """Raison de refus d'un nom de preset personnalisé, None si valide.

    `customs` est la collection des noms déjà pris (dict ou liste).
    """
    if not name.strip():
        return t("presets.err_empty")
    if name in reserved_names():
        return t("presets.err_reserved")
    if name in customs:
        return t("presets.err_taken")
    return None


class PresetController:
    """Fusion des presets intégrés (moteur/) et personnalisés (config).

    Objet sans état propre : chaque lecture passe par le ConfigStore, deux
    instances sur la même config sont interchangeables.
    """

    def __init__(self, config):
        self._config = config

    def _customs(self) -> dict:
        # dict nom → params ; une config pré-phase-4 peut encore contenir
        # la liste par défaut de l'époque — ignorée.
        customs = self._config.get("custom_presets")
        return customs if isinstance(customs, dict) else {}

    # ── Lecture ───────────────────────────────────────────────────────────
    def keys(self) -> list[str]:
        """Toutes les clés : intégrés d'abord, personnalisés ensuite."""
        return list(PRESETS) + self.custom_names()

    def custom_names(self) -> list[str]:
        return list(self._customs())

    def display_name(self, key: str) -> str:
        if key in PRESETS:
            return t(f"presets.builtin.{key}")
        return key

    def resolve(self, display: str) -> str | None:
        """Clé d'après le libellé affiché (None si inconnu)."""
        for key in self.keys():
            if self.display_name(key) == display:
                return key
        return None

    def params(self, key: str) -> dict | None:
        if key in PRESETS:
            return dict(PRESETS[key])
        params = self._customs().get(key)
        return dict(params) if params else None

    def matching(self, params: dict) -> str | None:
        """Clé du preset aux réglages strictement identiques, sinon None.

        Les jeux de clés doivent coïncider : un preset binaire n'a pas
        color_precision/layer_difference, un preset couleur les exige.
        """
        for key in self.keys():
            preset = self.params(key)
            if preset is None or set(preset) != set(params):
                continue
            if all(_equal(preset[k], params[k]) for k in preset):
                return key
        return None

    # ── Écriture (personnalisés uniquement) ───────────────────────────────
    def _name_conflict(self, name: str, customs: dict) -> bool:
        return (not name or name in reserved_names() or name in customs)

    def save(self, name: str, params: dict) -> bool:
        if self._name_conflict(name, self._customs()):
            return False
        self._config.set("custom_presets", name, dict(params))
        return True

    def rename(self, old: str, new: str) -> bool:
        customs = self._customs()
        if old not in customs or self._name_conflict(new, customs):
            return False
        # Reconstruit le dict : le preset garde sa position dans la liste.
        rebuilt = {new if k == old else k: v for k, v in customs.items()}
        self._config.set("custom_presets", None, rebuilt)
        return True

    def delete(self, name: str) -> bool:
        if name not in self._customs():
            return False
        self._config.remove("custom_presets", name)
        return True
