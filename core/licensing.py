"""Licence Pro — API licences Lemon Squeezy, sans dépendance GUI.

Tout le traitement d'images reste hors-ligne : seul l'état de la licence
appelle le serveur (activate / validate / deactivate). Les résultats sont
toujours livrés via `on_done(ok, message)` :
- scheduler fourni (GUI)  → requête en thread daemon, callback via after(0) ;
- scheduler None (CLI/tests) → exécution synchrone, callback appelé inline.

L'état « Pro » est purement local (is_pro) : clé présente ET (validée il y a
moins de 7 jours OU dernier succès — activation ou validation — de moins de
30 jours — grâce hors-ligne). Une réponse serveur formelle d'invalidité est
la seule chose qui purge ; pas de réseau n'y change rien.
"""

import json
import socket
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from core.constants import LS_API_BASE
from core.i18n import t

VALIDATE_AFTER = timedelta(days=7)   # revalidation hebdomadaire
GRACE = timedelta(days=30)           # grâce hors-ligne après activation
TIMEOUT = 15                         # secondes
WEEK_MS = 7 * 24 * 3600 * 1000


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse(ts) -> datetime | None:
    try:
        return datetime.fromisoformat(ts or "")
    except (TypeError, ValueError):
        return None


def _latest(*dts: datetime | None) -> datetime | None:
    """Le plus récent des horodatages fournis (None s'ils sont tous vides)."""
    known = [d for d in dts if d is not None]
    return max(known) if known else None


class LicenseManager:
    """Activate/validate/deactivate + état local persisté (config « pro »)."""

    def __init__(self, config, scheduler=None):
        self._config = config
        self._scheduler = scheduler
        self._busy = False  # une requête réseau à la fois (côté GUI)

    def set_scheduler(self, scheduler) -> None:
        """Branché par l'app une fois la fenêtre créée (app.after)."""
        self._scheduler = scheduler

    # ── État local ────────────────────────────────────────────────────────
    def stored_key(self) -> str:
        return (self._config.get("pro", "license_key", "") or "").strip()

    def is_pro(self) -> bool:
        if not self.stored_key():
            return False
        now = datetime.now()
        validated = _parse(self._config.get("pro", "last_validated_at", ""))
        if validated and now - validated < VALIDATE_AFTER:
            return True
        # Grâce hors-ligne : ancrée sur le DERNIER SUCCÈS (validation ou
        # activation) — un client qui validait chaque semaine puis s'absente
        # garde ses 30 jours complets, même bien après l'activation.
        last = _latest(validated,
                       _parse(self._config.get("pro", "activated_at", "")))
        return bool(last and now - last < GRACE)

    def _purge(self) -> None:
        for key in ("license_key", "instance_id", "activated_at",
                    "last_validated_at"):
            self._config.set("pro", key, "")

    # ── Réseau ────────────────────────────────────────────────────────────
    def _post(self, endpoint: str, payload: dict) -> tuple[bool, dict]:
        """POST form-encodé → (True, réponse) | (False, {"error": message}).

        Lemon Squeezy renvoie les refus en 4xx avec du JSON {"error": ...}
        — jamais d'exception si le corps se lit ; sinon message réseau.
        """
        data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{LS_API_BASE}/licenses/{endpoint}", data=data, method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
                return True, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Messages réseau traduits À L'ÉMISSION (t() sûr depuis la
            # thread réseau : échange atomique du dict de langue).
            try:
                body = json.loads(exc.read().decode("utf-8"))
                message = body.get("error") or t("license.msg.http_error",
                                                 code=exc.code)
            except (ValueError, AttributeError):
                message = t("license.msg.http_error", code=exc.code)
            return False, {"error": message}
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError):
            return False, {"error": t("license.msg.server_unreachable")}

    def _run(self, job, on_done) -> None:
        """job() → (ok, message), exécuté hors du thread GUI si possible."""
        if self._scheduler is None:
            on_done(job())
            return
        if self._busy:
            on_done((False, t("license.msg.busy")))
            return
        self._busy = True

        def worker():
            result = job()
            self._busy = False
            self._scheduler(0, lambda: on_done(result))

        threading.Thread(target=worker, daemon=True,
                         name="ptp-license").start()

    # ── Opérations ────────────────────────────────────────────────────────
    def activate(self, key: str, on_done) -> None:
        key = (key or "").strip()
        instance = (socket.gethostname() or "PixelToPath")[:50]

        def job():
            if not key:
                return False, t("license.msg.empty_key")
            ok, resp = self._post("activate", {
                "license_key": key, "instance_name": instance,
            })
            if not ok:
                return False, t("license.msg.refused",
                                reason=resp.get("error",
                                                t("license.msg.fallback")))
            if not resp.get("activated"):
                return False, t("license.msg.refused_server")
            instance_id = str((resp.get("instance") or {}).get("id", ""))
            self._config.set("pro", "license_key", key)
            self._config.set("pro", "instance_id", instance_id)
            self._config.set("pro", "activated_at", _now())
            self._config.set("pro", "last_validated_at", _now())
            return True, t("license.msg.activated")

        self._run(job, on_done)

    def validate(self, on_done) -> None:
        """Revalidation : ne purge qu'en cas de réponse formelle d'invalidité.

        Hors-ligne → rien ne change (la grâce locale s'applique toujours).
        """
        key, instance_id = self.stored_key(), \
            self._config.get("pro", "instance_id", "")

        def job():
            if not key:
                return False, t("license.msg.nothing_to_check")
            ok, resp = self._post("validate", {
                "license_key": key, "instance_id": instance_id,
            })
            if not ok:
                return True, t("license.msg.offline")
            # `valid: true` ne suffit pas : une clé désactivée en store
            # renvoie valid avec status ≠ active.
            license_key = resp.get("license_key") or {}
            if resp.get("valid") and license_key.get("status") == "active":
                self._config.set("pro", "last_validated_at", _now())
                return True, t("license.msg.verified")
            self._purge()
            return False, t("license.msg.inactive")

        self._run(job, on_done)

    def deactivate(self, on_done) -> None:
        """Libère un siège : ne purge le local qu'en cas de succès serveur."""
        key, instance_id = self.stored_key(), \
            self._config.get("pro", "instance_id", "")

        def job():
            ok, resp = self._post("deactivate", {
                "license_key": key, "instance_id": instance_id,
            })
            if not ok:
                return False, t("license.msg.deactivate_failed",
                                reason=resp.get("error",
                                                t("license.msg.fallback")))
            self._purge()
            return True, t("license.msg.deactivated")

        self._run(job, on_done)

    # ── Revalidation périodique (GUI) ─────────────────────────────────────
    def maybe_revalidate(self, on_done) -> bool:
        """Revalide si la dernière vérification date de plus de 7 jours."""
        if not self.stored_key() or self._busy:
            return False
        validated = _parse(self._config.get("pro", "last_validated_at", ""))
        if validated and datetime.now() - validated < VALIDATE_AFTER:
            return False
        self.validate(on_done)
        return True

    def start_periodic_validation(self, on_done=None) -> None:
        """Revalidation hebdomadaire. `on_done(ok, message)` permet au shell
        de rafraîchir l'UI quand l'état bascule (purge détectée côté serveur) ;
        absent → réponse ignorée (comportement d'origine)."""
        if self._scheduler is None:
            return
        on_done = on_done or (lambda _ok, _msg: None)

        def tick():
            self.maybe_revalidate(on_done)
            self._scheduler(WEEK_MS, tick)

        self._scheduler(WEEK_MS, tick)
