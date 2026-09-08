"""Constantes globales de l'application (aucune dépendance GUI)."""

APP_NAME = "PixelToPath"
APP_VERSION = "3.0.0"

# Extensions d'images acceptées en entrée
IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

# ── Licences (Lemon Squeezy) ─────────────────────────────────────────────────
LS_API_BASE = "https://api.lemonsqueezy.com/v1"
# Page Pro du site : le checkout Lemon Squeezy y est intégré (la vente
# envoie la licence par e-mail ; l'application n'a plus qu'à l'activer).
LS_CHECKOUT_URL = "https://pixel-to-path.com/pro/"

# ── Monétisation / partenaires ───────────────────────────────────────────────
PAYPAL_URL = "https://www.paypal.com/donate/?hosted_button_id=6TCT576QMTBAL"
DOCUNEST_URL = "https://docunest.app"
# Rangée d'affiliés de la vue Partenaires : désactivée tant que les liens
# ne pointent pas vers de vraies URLs d'affiliation. Passer à True (et
# compléter AFFILIATE_URLS) suffit à la réafficher — le design est gardé
# dans partners_view._build_affiliates().
AFFILIATES_ENABLED = False
# TODO: compléter avec les identifiants d'affiliation.
AFFILIATE_URLS = {
    "cricut": "https://cricut.com",
    "lightburn": "https://lightburnsoftware.com",
}
