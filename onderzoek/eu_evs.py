"""Haalt de maandcijfers per model op bij eu-evs.com, met het account uit .env.

Registraties per model en per land zijn een sterker signaal voor belangstelling dan
YouTube-weergaven: het zijn verkochte auto's. De CSV is gegevens uit een account en gaat
**niet** in de publieke repo: hij landt in raw/data/eu-evs/ (gitignored) en wordt intern
gebruikt, net als EV Database. Een wiki-pagina mag een enkel cijfer noemen, met bron.

Eén download per maand: eu-evs.com zet /premiumExport in robots.txt voor crawlers. Dit is
geen crawler maar het eigen account dat de export ophaalt die het mag ophalen; daarom één
bestand, alleen als er deze maand nog geen is, en verder geen pagina's van de site.

    uv run --no-project --with requests python onderzoek/eu_evs.py [--forceer]
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[1]
DOEL = REPO / "raw" / "data" / "eu-evs"
BASIS = "https://eu-evs.com"
EXPORTS = {"modellen-maand": "/premiumExportModelsMonthly"}
UA = "ev-wiki-onderzoeker/1.0 (+https://github.com/businessdatasolutions/ev-wiki)"


def lees_env() -> dict[str, str]:
    """`.env` met regels SLEUTEL=waarde; spaties rond `=` en aanhalingstekens mogen."""
    env = {}
    for regel in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in regel and not regel.lstrip().startswith("#"):
            k, v = regel.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def inloggen(s: requests.Session, email: str, wachtwoord: str) -> None:
    r = s.get(f"{BASIS}/login", timeout=30)
    r.raise_for_status()
    token = re.search(r'name="_token" value="([^"]+)"', r.text)
    if not token:
        raise RuntimeError("geen _token op de inlogpagina; is de pagina veranderd?")
    r = s.post(f"{BASIS}/login", data={"_token": token.group(1), "email": email, "password": wachtwoord},
               headers={"Referer": f"{BASIS}/login"}, timeout=30)
    r.raise_for_status()
    if "/login" in r.url or 'name="password"' in r.text:
        raise RuntimeError("inloggen mislukt: controleer EU_EVS_E_MAIL en EU_EVS_PASSWORD in .env")


def haal(s: requests.Session, naam: str, pad: str, maand: str) -> Path:
    r = s.get(f"{BASIS}{pad}", timeout=120)
    soort = r.headers.get("Content-Type", "")
    if "Premium access is not active" in r.text:
        # Gezien 06-10-2026: het gratis account logt in, maar de CSV-exports zitten in Premium.
        raise RuntimeError(f"{naam}: Premium is niet actief voor dit account; de CSV-export vraagt een abonnement")
    if r.status_code != 200 or "html" in soort.lower():
        raise RuntimeError(f"{naam}: geen CSV (HTTP {r.status_code}, {soort})")
    DOEL.mkdir(parents=True, exist_ok=True)
    pad_uit = DOEL / f"{maand}-{naam}.csv"
    pad_uit.write_bytes(r.content)
    return pad_uit


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--forceer", action="store_true", help="ook ophalen als deze maand al een bestand heeft")
    args = ap.parse_args()

    maand = dt.date.today().strftime("%Y-%m")
    te_doen = {n: p for n, p in EXPORTS.items() if args.forceer or not (DOEL / f"{maand}-{n}.csv").exists()}
    if not te_doen:
        print(f"eu-evs: {maand} al opgehaald")
        return 0
    env = lees_env()
    email, wachtwoord = env.get("EU_EVS_E_MAIL"), env.get("EU_EVS_PASSWORD")
    if not email or not wachtwoord:
        print("eu-evs: EU_EVS_E_MAIL of EU_EVS_PASSWORD ontbreekt in .env", file=sys.stderr)
        return 1
    with requests.Session() as s:
        s.headers["User-Agent"] = UA
        try:
            inloggen(s, email, wachtwoord)
            for naam, pad in te_doen.items():
                uit = haal(s, naam, pad, maand)
                regels = uit.read_text(encoding="utf-8", errors="replace").count("\n")
                print(f"eu-evs: {uit.relative_to(REPO)} ({regels} regels)")
        except (RuntimeError, requests.RequestException) as e:
            print(f"eu-evs: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
