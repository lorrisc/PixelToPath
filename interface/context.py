"""Contexte applicatif partagé — passe une seule fois à chaque vue/widget.

Regroupe les services sans GUI : config persistée, dossier temporaire.
Les champs « service » (presets, licence, worker) sont branchés par les
phases suivantes ; les vues les lisent via ctx, jamais en import direct,
ce qui garde les vues testables et la CLI indépendante de interface/.
"""

from dataclasses import dataclass
from pathlib import Path

from core.config import ConfigStore


@dataclass
class AppContext:
    config: ConfigStore
    temp_dir: Path
    # Branchés plus tard (phases 4-6) — None tant que non initialisés.
    presets: object | None = None
    license: object | None = None
    worker: object | None = None
    # Gestionnaire des hot folders (branché par main()) : la surveillance
    # vit au niveau de l'application — hors des vues, y compris quand la
    # fenêtre est masquée dans la barre système.
    hotfolders: object | None = None
    # StatusBar de l'app (branché par App._build_interface) : les vues y
    # publient leur état ; l'app ne dépend pas d'elles pour l'afficher.
    status: object | None = None

    def is_pro(self) -> bool:
        return bool(self.license is not None and self.license.is_pro())
