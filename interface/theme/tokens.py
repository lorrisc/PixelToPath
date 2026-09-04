"""Tokens de couleur light/dark + ThemeService.

Deux couches de thème cohabitent :
1. Le json ctk (pixeltopath.json) habille tous les widgets customtkinter —
   chaque couleur y est une paire [light, dark] et bascule toute seule via
   ctk.set_appearance_mode().
2. Les tokens ci-dessous servent aux éléments que le json n'atteint pas
   (CTkCanvas, damier, statuts, art du dropzone…). Les widgets concernés
   implémentent apply_theme(tokens) et ThemeService.apply_all() les parcourt
   après chaque bascule.

Règle : toute couleur explicite hors json passe par ces tokens — jamais un
hex nu figé à la construction, qui ne basculerait pas avec le mode.
"""

import customtkinter as ctk

LIGHT = {
    # Surfaces
    "bg":            "#f7f7f7",
    "surface":       "#ffffff",
    "rail":          "#fafafa",
    "border":        "#e8e8e8",
    "border_strong": "#d8d8d8",
    # Texte
    "text":          "#333333",
    "heading":       "#2c3e50",
    "muted":         "#666666",
    "faint":         "#aaaaaa",
    # Marque
    "primary":       "#ff9900",
    "primary_hover": "#e68a00",
    "primary_tint":  "#fff8ee",
    "on_primary":    "#ffffff",
    "ring":          "#ffe0a0",
    # États
    "success":       "#2e7d32",
    "live":          "#4caf7d",
    "warn":          "#e09a00",
    "error":         "#c62828",
    # Éléments spécifiques
    "checker_a":     "#f5f5f5",
    "checker_b":     "#ffffff",
    "seg_track":     "#f0f0f0",
    "seg_selected":  "#2c3e50",
    "switch_off":    "#dddddd",
    "tooltip_bg":    "#18181b",
    "tooltip_text":  "#f4f4f5",
    "canvas":        "#f0f0f0",
}

DARK = {
    "bg":            "#131a23",
    "surface":       "#1c2733",
    "rail":          "#18212c",
    "border":        "#2c3a49",
    "border_strong": "#3a4552",
    "text":          "#e8edf2",
    "heading":       "#f2f5f8",
    "muted":         "#93a1b1",
    "faint":         "#5d6b7a",
    "primary":       "#ff9900",
    "primary_hover": "#ffb14d",
    "primary_tint":  "#2a2415",
    "on_primary":    "#ffffff",
    "ring":          "#5c4a1e",
    "success":       "#5cbd8c",
    "live":          "#4caf7d",
    "warn":          "#e0a93a",
    "error":         "#e05252",
    "checker_a":     "#232b35",
    "checker_b":     "#1a212a",
    "seg_track":     "#26313d",
    "seg_selected":  "#ff9900",
    "switch_off":    "#37424e",
    "tooltip_bg":    "#18181b",
    "tooltip_text":  "#f4f4f5",
    "canvas":        "#161d26",
}

# Paires [light, dark] prêtes pour un configure() explicite — à utiliser
# lorsqu'un widget doit porter une couleur hors json tout en basculant.
def pair(key: str) -> list[str]:
    return [LIGHT[key], DARK[key]]


class ThemeService:
    """État du thème courant + diffusion aux widgets « theme-aware »."""

    _mode: str = "Light"  # "Light" | "Dark"

    @classmethod
    def mode(cls) -> str:
        return cls._mode

    @classmethod
    def is_dark(cls) -> bool:
        return cls._mode == "Dark"

    @classmethod
    def tokens(cls) -> dict:
        return DARK if cls.is_dark() else LIGHT

    @classmethod
    def color(cls, key: str) -> str:
        return cls.tokens()[key]

    @classmethod
    def set_mode(cls, mode: str, root=None) -> None:
        """Bascule l'apparence puis re-habille les widgets hors json."""
        cls._mode = "Dark" if mode == "Dark" else "Light"
        ctk.set_appearance_mode(cls._mode)
        if root is not None:
            cls.apply_all(root)

    @classmethod
    def toggle(cls, root=None) -> str:
        cls.set_mode("Light" if cls.is_dark() else "Dark", root)
        return cls._mode

    @classmethod
    def apply_all(cls, widget) -> None:
        """Parcourt l'arbre et appelle apply_theme(tokens) quand défini.

        CTkFrame / CTkCanvas ne propagent pas le mode : les widgets qui
        dessinent eux-mêmes (canvas, damier, rail) exposent apply_theme().
        """
        fn = getattr(widget, "apply_theme", None)
        if callable(fn):
            fn(cls.tokens())
        for child in widget.winfo_children():
            cls.apply_all(child)
