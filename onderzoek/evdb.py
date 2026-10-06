"""Een model naslaan bij EV Database, **alleen ter controle** (CLAUDE.md §Verzamelaar, interne bronnen).

Besluit eigenaar (06-10-2026): EV Database wordt alleen intern gebruikt om fabrieksopgaven uit
transcripts te controleren. Dit script toont de waarden in de terminal en schrijft **niets** weg:
geen bestand, geen register, niets in raw/ of wiki/. Een wiki-pagina zegt hooguit "gecontroleerd tegen
EV Database op <datum>". Het is een commerciële databank (databankenrecht): sla per keer één model na,
geen hele lijsten.

    uv run --no-project python onderzoek/evdb.py "Skoda Epiq"
    uv run --no-project python onderzoek/evdb.py "Kia EV2" --velden accu,wltp,kofferbak
"""
from __future__ import annotations

import argparse
import html as _html
import re
import sys
import time
import unicodedata
import urllib.request

SITEMAP = "https://ev-database.org/sitemap.xml"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0 Safari/537.36"
MAX_UITVOERINGEN = 6   # één model naslaan, geen lijsten
PAUZE_S = 2.0

# Veld in de uitvoer → label op de pagina (Engels). Volgorde = volgorde van de tabel.
VELDEN = {
    "accu": "Useable Battery",
    "wltp": "Range",                 # onder "WLTP Ratings"
    "realistisch": "Real Range",     # schatting van EV Database, geen meting
    "verbruik": "Efficiency",
    "dc": "Charge Power (max)",
    "dc-10-80": "Charge Time (10->80%)",
    "ac": "Charge Power",
    "kofferbak": "Cargo Volume",
    "kofferbak-max": "Cargo Volume Max",
    "frunk": "Cargo Volume Frunk",
    "trekhaak": "Tow Hitch Possible",
    "trek-geremd": "Towing Weight Braked",
    "trek-ongeremd": "Towing Weight Unbraked",
    "zitplaatsen": "Seats",
    "prijs-nl": "The Netherlands",
}


def plat(t: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def haal(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def regels(html: str) -> list[str]:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    t = _html.unescape(re.sub(r"<[^>]+>", "\n", t))
    return [l.strip() for l in t.split("\n") if l.strip()]


def waarde(rs: list[str], label: str, na: str | None = None) -> str:
    """De waarde vóór of na een label. EV Database zet de waarde in de kop vóór het label
    ("235 km * | Real Range") en in de tabellen erna ("Range | 310 km")."""
    start = rs.index(na) if na and na in rs else 0
    for i in range(start, len(rs)):
        if rs[i] == label:
            if label in ("Useable Battery", "Real Range", "Efficiency") and i > 0 and i < 40:
                return rs[i - 1].rstrip(" *")
            return rs[i + 1] if i + 1 < len(rs) else "?"
    return "-"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("model", help='merk en model, bijv. "Skoda Epiq"')
    ap.add_argument("--velden", help="komma-lijst uit: " + ", ".join(VELDEN))
    args = ap.parse_args()
    velden = [v.strip() for v in args.velden.split(",")] if args.velden else list(VELDEN)

    zoek = plat(args.model).split()
    urls = [u for u in re.findall(r"<loc>([^<]+/car/\d+/[^<]+)</loc>", haal(SITEMAP))
            if all(w in plat(u.rsplit("/", 1)[-1]) for w in zoek)]
    if not urls:
        print(f"niets gevonden voor '{args.model}'", file=sys.stderr)
        return 1
    if len(urls) > MAX_UITVOERINGEN:
        print(f"{len(urls)} uitvoeringen; de eerste {MAX_UITVOERINGEN} (maak de zoekvraag preciezer)", file=sys.stderr)
        urls = urls[:MAX_UITVOERINGEN]
    rijen = []
    for u in urls:
        time.sleep(PAUZE_S)
        rs = regels(haal(u))
        r = {"uitvoering": u.rsplit("/", 1)[-1].replace("-", " ")}
        for v in velden:
            if v == "dc-10-80":
                # Het label noemt per uitvoering het bereik ("Charge Time (23->188 km)"); het staat
                # direct na "Charge Power (10-80%)".
                i = rs.index("Charge Power (10-80%)") if "Charge Power (10-80%)" in rs else -1
                j = next((k for k in range(i + 1, len(rs)) if rs[k].startswith("Charge Time (")), None) if i >= 0 else None
                r[v] = rs[j + 1] if j is not None else "-"
                continue
            na = {"wltp": "WLTP Ratings", "prijs-nl": "Price"}.get(v)
            r[v] = waarde(rs, VELDEN[v], na)
        rijen.append(r)
    kolommen = ["uitvoering"] + velden
    breed = {k: max(len(k), *(len(str(r[k])) for r in rijen)) for k in kolommen}
    print("  ".join(k.ljust(breed[k]) for k in kolommen))
    for r in rijen:
        print("  ".join(str(r[k]).ljust(breed[k]) for k in kolommen))
    print("\nBron: EV Database, alleen ter controle; niet overnemen in de wiki ('realistisch' is hun schatting, geen meting).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
