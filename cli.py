"""PixelToPath CLI (Pro) — `ptp`.

N'importe jamais interface/ : core/ + moteur/ uniquement. Les licences
passent par le mode synchrone du LicenseManager (scheduler=None) —
chaque commande attend la réponse serveur, sans GUI ni threads.

Exits : 0 succès · 1 erreur de conversion · 2 licence manquante / usage.
"""

import argparse
import os
import shutil
import sys
import tempfile

from core.config import ConfigStore
from core.convert_service import (
    convert_file,
    next_output_path,
    prepare_input,
)
from core.constants import APP_NAME, APP_VERSION, LS_CHECKOUT_URL
from core import i18n
from core.i18n import t, tp
from core.licensing import LicenseManager
from core.presets import PresetController
from PIL import Image


def _parse_value(raw: str):
    """`--set length_threshold=4.5` : int, puis float, puis chaîne."""
    for cast in (int, float):
        try:
            return cast(raw)
        except ValueError:
            continue
    return raw


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ptp",
        description=t("cli.desc", app=APP_NAME, version=APP_VERSION),
    )
    parser.add_argument("--version", action="version",
                        version=f"{APP_NAME} {APP_VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_conv = sub.add_parser("convert", help=t("cli.convert_help"))
    p_conv.add_argument("inputs", nargs="+", metavar="IMAGE",
                        help=t("cli.inputs_help"))
    p_conv.add_argument("-o", "--output", required=True, metavar="DIR",
                        help=t("cli.output_help"))
    p_conv.add_argument("--preset", default="bw", metavar="NOM",
                        help=t("cli.preset_help"))
    p_conv.add_argument("--colormode", choices=("binary", "color"),
                        help=t("cli.override_help"))
    p_conv.add_argument("--mode", choices=("spline", "polygon", "none"),
                        help=t("cli.override_help"))
    p_conv.add_argument("--invert", action="store_true",
                        help=t("cli.invert_help"))
    p_conv.add_argument("--set", dest="overrides", action="append",
                        metavar="CLE=VALEUR", default=[],
                        help=t("cli.set_help"))

    p_lic = sub.add_parser("license", help=t("cli.license_help"))
    lic = p_lic.add_subparsers(dest="license_command", required=True)
    p_act = lic.add_parser("activate", help=t("cli.activate_help"))
    p_act.add_argument("key", metavar="CLE")
    lic.add_parser("deactivate", help=t("cli.deactivate_help"))
    lic.add_parser("status", help=t("cli.status_help"))
    return parser


# ── Licence ──────────────────────────────────────────────────────────────────
def cmd_license(args, manager: LicenseManager) -> int:
    result = []
    if args.license_command == "activate":
        manager.activate(args.key, lambda r: result.append(r))
        ok, message = result[0]
        print(message)
        return 0 if ok else 1
    if args.license_command == "deactivate":
        manager.deactivate(lambda r: result.append(r))
        ok, message = result[0]
        print(message)
        return 0 if ok else 1

    # status
    config = manager._config
    key = manager.stored_key()
    if not key:
        print(t("license.free_line"))
        print(t("license.goto_pro", url=LS_CHECKOUT_URL))
        return 0
    state = t("license.state_active") if manager.is_pro() \
        else t("license.state_expired")
    print(t("license.state_line", state=state,
            tail=key[-4:] if len(key) >= 4 else ""))
    print(t("license.activated_at", date=_date_or_dash(
        config.get("pro", "activated_at", ""))))
    print(t("license.last_validated", date=_date_or_dash(
        config.get("pro", "last_validated_at", ""))))
    return 0


def _date_or_dash(iso: str) -> str:
    """L'horodatage brut est conservé sur la CLI (précision complète)."""
    return iso or "—"


# ── Conversion ───────────────────────────────────────────────────────────────
def _params_for(args, presets: PresetController) -> dict:
    params = presets.params(args.preset)
    if params is None:
        available = ", ".join(presets.keys())
        raise SystemExit(t("cli.unknown_preset", name=args.preset,
                           available=available))
    if args.colormode:
        params["colormode"] = args.colormode
    if args.mode:
        params["mode"] = args.mode
    for override in args.overrides:
        key, sep, value = override.partition("=")
        if not sep:
            raise SystemExit(t("cli.bad_set", value=override))
        params[key.strip()] = _parse_value(value.strip())
    return params


def cmd_convert(args, manager: LicenseManager, config: ConfigStore) -> int:
    if not manager.is_pro():
        print(t("cli.pro_only"))
        print(t("license.goto_pro", url=LS_CHECKOUT_URL))
        print(t("cli.pro_hint"))
        return 2

    presets = PresetController(config)
    try:
        params = _params_for(args, presets)
    except SystemExit as exc:
        print(exc)
        return 2

    os.makedirs(args.output, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix="ptp-")
    errors = 0
    for index, raw in enumerate(args.inputs, 1):
        input_path = os.path.normpath(raw)
        name = os.path.basename(input_path)
        if not os.path.isfile(input_path):
            print(f"{t('cli.progress', i=index, n=len(args.inputs))} "
                  f"{t('cli.err')}   {name} : {t('cli.err_missing')}")
            errors += 1
            continue
        stem = os.path.splitext(name)[0]
        output_path = next_output_path(args.output, stem)
        try:
            colormode = params.get("colormode", "color")
            if colormode == "binary" or args.invert:
                # binary : aplatir sur blanc (et inverser si demandé) —
                # même préparation que l'interface.
                with Image.open(input_path) as img:
                    tmp = prepare_input(img, temp_dir, colormode=colormode,
                                        invert=args.invert)
                convert_file(tmp, output_path, params)
            else:
                convert_file(input_path, output_path, params)
            print(f"{t('cli.progress', i=index, n=len(args.inputs))} "
                  f"{t('cli.ok').ljust(8, ' ')} {name} → {output_path}")
        except BaseException as exc:  # paniques pyo3 comprises
            message = str(exc) or exc.__class__.__name__
            print(f"{t('cli.progress', i=index, n=len(args.inputs))} "
                  f"{t('cli.err')}   {name} : {message}")
            errors += 1
    shutil.rmtree(temp_dir, ignore_errors=True)
    total = len(args.inputs) - errors
    print(tp("cli.summary", total, done=total, total=len(args.inputs),
             dir=args.output))
    return 1 if errors else 0


def main(argv=None) -> int:
    # Sortie console en UTF-8 : sous Windows, une sortie redirigée (|, >)
    # utilise le codepage locale (cp1252) qui ne peut pas encoder les
    # flèches de l'aide/messages i18n → UnicodeEncodeError. Sur la console
    # réelle (PEP 528) et sous Linux, c'est un no-op.
    for _stream in (sys.stdout, sys.stderr):
        if _stream is not None and hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    config = ConfigStore()
    # Langue AVANT build_parser : l'aide argparse est figée à la construction.
    i18n.install_from_config(config)
    args = build_parser().parse_args(argv)
    manager = LicenseManager(config)  # pas de scheduler : synchrone
    if args.command == "license":
        return cmd_license(args, manager)
    return cmd_convert(args, manager, config)


if __name__ == "__main__":
    sys.exit(main())
