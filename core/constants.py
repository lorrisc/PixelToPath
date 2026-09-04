"""Constantes globales de l'application (aucune dépendance GUI)."""

APP_NAME = "PixelToPath"
APP_VERSION = "3.0.0"

# Extensions d'images acceptées en entrée
IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

# ── Licences (Lemon Squeezy) ─────────────────────────────────────────────────
LS_API_BASE = "https://api.lemonsqueezy.com/v1"
# TODO: URL de checkout Pro réelle du store Lemon Squeezy (la vente envoie la
# licence par e-mail ; l'application n'aura plus qu'à l'activer).
LS_CHECKOUT_URL = "https://pixel-to-path.com/#pro"

# ── Monétisation / partenaires ───────────────────────────────────────────────
PAYPAL_URL = "https://www.paypal.com/donate/?hosted_button_id=6TCT576QMTBAL"
DOCUNEST_URL = "https://docunest.app"
# TODO: compléter avec les identifiants d'affiliation.
AFFILIATE_URLS = {
    "cricut": "https://cricut.com",
    "lightburn": "https://lightburnsoftware.com",
}
