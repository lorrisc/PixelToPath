"""Chargement des icônes PNG light/dark en CTkImage (bascule automatique)."""

import customtkinter as ctk
from PIL import Image

from interface.utils import resource_path


def ctk_icon(name: str, size: int = 24) -> ctk.CTkImage:
    """Icône `interface/assets/icons/<name>_{light,dark}.png` en CTkImage."""
    light = Image.open(resource_path(f"interface/assets/icons/{name}_light.png"))
    dark = Image.open(resource_path(f"interface/assets/icons/{name}_dark.png"))
    return ctk.CTkImage(light_image=light, dark_image=dark, size=(size, size))


def ctk_picture(relative_path: str, size: tuple[int, int]) -> ctk.CTkImage:
    """Image fixe (capture, pastille logo) — identique en light et dark."""
    img = Image.open(resource_path(relative_path))
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)


def ctk_logo(name: str, height: int = 44) -> ctk.CTkImage:
    """Logo partenaire `interface/assets/partners/logo_<name>.png` —
    pastille blanche lisible sur les deux thèmes, une seule variante."""
    rel = f"interface/assets/partners/logo_{name}.png"
    img = Image.open(resource_path(rel))
    width = round(img.width * height / img.height)
    return ctk_picture(rel, (width, height))


def ctk_flag(code: str, size: tuple[int, int] = (24, 18)) -> ctk.CTkImage:
    """Drapeau de langue `interface/assets/flags/<code>.png` (généré par
    scripts/gen_flags.py) — identique en light et dark, liseré neutre."""
    return ctk_picture(f"interface/assets/flags/{code}.png", size)
