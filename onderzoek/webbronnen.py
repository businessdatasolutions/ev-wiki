"""Webbronnen voor de verzamelaar: geschreven reviews en themaartikelen (CLAUDE.md §Verzamelaar).

Per site in `web:` van onderzoek/kanalen.yaml:

- **Nieuwste reviews** (elke run): de overzichtspagina, links die op `review_patroon` passen.
- **Oudere reviews** (alleen bij een verkenning): de knooppunten en de artikelen uit de sitemap die
  op `sitemap_patroon` passen, daarin de modelpagina's (`modelpagina_patroon`), en daarop de link
  naar de review. Zo vindt de verzamelaar reviews die niet meer op de overzichtspagina staan.
- **Themaartikelen** (`artikelen:`): een vaste lijst, opnieuw opgehaald na `ververs_dagen`.

Een review telt alleen als de titel een model uit de sitemap van Plinkie noemt (zelfde koppeling
als bij YouTube). De tekst gaat via trafilatura naar markdown in raw/articles/, met een kop volgens
het artikelcontract in CLAUDE.md. Alles komt in onderzoek/register.jsonl, met `url` als sleutel.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
import time
import urllib.request
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
RAW_ARTIKELEN = REPO / "raw" / "articles"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0 Safari/537.36"
PAUZE_S = 2.0
MAANDEN = {m: i for i, m in enumerate(["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
                                        "september", "oktober", "november", "december"], start=1)}


def haal_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "nl-NL,nl;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def absoluut(basis: str, pad: str) -> str:
    pad = pad.replace("&amp;", "&")
    if pad.startswith("http"):
        return pad
    m = re.match(r"(https?://[^/]+)", basis)
    return m.group(1) + pad


def links(html: str, basis: str, patroon: str) -> list[str]:
    gevonden = re.findall(rf'href="((?:https?://[^"/]+)?{patroon})"', html)
    return list(dict.fromkeys(absoluut(basis, g).split("#")[0] for g in gevonden))


def platte_tekst(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    import html as _h
    return re.sub(r"\n\s*\n+", "\n", _h.unescape(t))


def kenmerken(html: str) -> dict:
    """Wat ANWB naast de tekst zet: uitvoering, auteur, publicatiedatum (\"Gepubliceerd op 28 juni 2023\")."""
    t = platte_tekst(html)
    uit = {}
    m = re.search(r"\nUitvoering\n([^\n]+)\n([^\n]+)\n([^\n]+)\n", t)
    if m:
        uit["uitvoering"] = m.group(1).strip()
        uit["auteur"] = m.group(2).strip()
    m = re.search(r"Gepubliceerd op\n\s*(\d{1,2}) (\w+) (\d{4})", t)
    if m and m.group(2).lower() in MAANDEN:
        uit["date_published"] = dt.date(int(m.group(3)), MAANDEN[m.group(2).lower()], int(m.group(1))).isoformat()
    return uit


def naar_markdown(html: str, url: str) -> tuple[str, dict]:
    import trafilatura
    md = trafilatura.extract(html, output_format="markdown", include_tables=True, include_links=False,
                             with_metadata=True, url=url) or ""
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", md, re.S)
    if m:
        meta, md = yaml.safe_load(m.group(1)) or {}, m.group(2)
    # Het blok "andere tests" en de webwinkelpromotie onderaan zijn geen inhoud.
    md = re.split(r"\n## (Bekijk andere tests|We hebben nog veel meer getest)", md)[0].strip()
    return md, meta


def slugify(t: str) -> str:
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").lower()
    return "-".join(w for w in re.split(r"[^a-z0-9]+", t) if w)[:90].strip("-")


def schrijf_raw(pad: Path, kop: dict, body: str) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    tekst = "---\n" + yaml.safe_dump(kop, allow_unicode=True, sort_keys=False, width=1000).rstrip() + "\n---\n\n" + body + "\n"
    pad.write_text(tekst, encoding="utf-8")


def haal_pagina(url: str, site: dict, soort: str, modellen: list[str], droog: bool, html: str | None = None) -> tuple[str, str | None]:
    """Eén review of artikel schrijven (de HTML mag al opgehaald zijn). Geeft (status, bestand of reden)."""
    html = html or haal_html(url)
    body, meta = naar_markdown(html, url)
    if len(body) < 500:
        return "mislukt", "te weinig tekst uit de pagina gehaald"
    titel = (re.search(r"^# (.+)$", body, re.M) or re.search(r"<title[^>]*>([^<]+)", html)).group(1).strip()
    k = kenmerken(html)
    vandaag = dt.date.today().isoformat()
    kop = {
        "title": titel,
        "url": url,
        "site": site["naam"],
        "soort": soort,
        "author": [k["auteur"]] if k.get("auteur") else [site["naam"]],
        "date_published": k.get("date_published") or str(meta.get("date") or ""),
        "uitvoering": k.get("uitvoering"),
        "taal": site.get("taal", "nl"),
        "opgehaald": vandaag,
        "verzameld": {"door": "verzamelaar", "datum": vandaag, "site": site["naam"],
                      "modellen_kandidaat": modellen, "status": "wacht op Process"},
        "notes": "Tekst uit de HTML gehaald met trafilatura; menu, voet en het blok met andere tests weggelaten. "
                 "Uitvoering, auteur en publicatiedatum uit de kenmerken naast de tekst.",
    }
    kop = {k2: v for k2, v in kop.items() if v not in (None, "")}
    naam = f"{slugify(site['naam'])}-{slugify(titel)}"
    pad = RAW_ARTIKELEN / f"{naam}.md"
    if droog:
        return "zou ophalen", str(pad.relative_to(REPO))
    schrijf_raw(pad, kop, body)
    return "opgehaald", str(pad.relative_to(REPO))


def sitemap_urls(site: dict) -> list[str]:
    """Alle URL's uit de (geneste) sitemap van de site die op sitemap_patroon passen."""
    patroon = site.get("sitemap_patroon")
    if not patroon or not site.get("sitemap"):
        return []
    xml = haal_html(site["sitemap"])
    subs = [u for u in re.findall(r"<loc>([^<]+)</loc>", xml) if site.get("sitemap_filter", "") in u]
    urls = []
    for s in dict.fromkeys(subs):
        time.sleep(PAUZE_S)
        urls += [u for u in re.findall(r"<loc>([^<]+)</loc>", haal_html(s)) if patroon in u]
    return list(dict.fromkeys(urls))


def web_run(sites: list[dict], modellen_alle: list[dict], modellen_in, reg: dict, max_ophalen: int,
            verkennen: bool, droog: bool) -> list[dict]:
    """Reviews en artikelen van alle webbronnen. `reg` heeft per url de laatste registerregel."""
    nieuw, opgehaald = [], 0
    vandaag = dt.date.today()
    for site in sites:
        kandidaten: list[tuple[str, str]] = []  # (url, soort)
        try:
            if site.get("overzicht"):
                kandidaten += [(u, "review") for u in links(haal_html(site["overzicht"]), site["overzicht"], site["review_patroon"])]
                time.sleep(PAUZE_S)
            if verkennen:
                knopen = list(site.get("knooppunten") or []) + sitemap_urls(site)
                modelpaginas = []
                for k in dict.fromkeys(knopen):
                    modelpaginas += links(haal_html(k), k, site["modelpagina_patroon"])
                    time.sleep(PAUZE_S)
                for mp in dict.fromkeys(modelpaginas):
                    sleutel = f"modelpagina:{mp}"
                    if sleutel in reg:
                        continue
                    kandidaten += [(u, "review") for u in links(haal_html(mp), mp, site["review_patroon"])]
                    # In het register, zodat een volgende verkenning deze pagina niet opnieuw leest.
                    reg[sleutel] = {"video_id": sleutel, "url": mp, "kanaal": site["naam"], "lijst": "web",
                                    "soort": "modelpagina", "status": "gelezen", "gezien": vandaag.isoformat()}
                    nieuw.append(reg[sleutel])
                    time.sleep(PAUZE_S)
                print(f"web {site['naam']}: {len(knopen)} knooppunten, {len(set(modelpaginas))} modelpagina's")
        except Exception as e:  # een site die faalt, houdt de rest niet tegen
            print(f"! web {site['naam']}: {e}", file=sys.stderr)
        for a in site.get("artikelen") or []:
            vorige = reg.get(a)
            oud = vorige and vorige.get("status") == "opgehaald" and \
                (vandaag - dt.date.fromisoformat(vorige.get("gezien", "2000-01-01"))).days >= int(site.get("ververs_dagen", 90))
            if not vorige or oud:
                kandidaten.append((a, "artikel"))
        for url, soort in dict.fromkeys(kandidaten):
            vorige = reg.get(url)
            if soort == "review" and vorige and not (vorige.get("status") == "mislukt" and vorige.get("pogingen", 1) < 3):
                continue
            if opgehaald >= max_ophalen:
                break
            regel = {"video_id": url, "url": url, "titel": None, "kanaal": site["naam"], "lijst": "web",
                     "soort": soort, "gezien": vandaag.isoformat()}
            try:
                html = haal_html(url)
                if soort == "review":
                    titel = re.sub(r"\s+[-|]\s+.*$", "", re.search(r"<title[^>]*>([^<]+)", html).group(1)).strip()  # niet knippen in "C-Klasse"
                    regel["titel"] = titel
                    mods = modellen_in(titel, modellen_alle)
                    if mods and "kwh" not in platte_tekst(html).lower():
                        # De koppeling laat algemene woorden weg ("Kona" voor kona-electric), dus
                        # een review van de benzineversie kan ook koppelen; een EV-review noemt kWh.
                        regel |= {"status": "overgeslagen", "reden": "geen kWh in de tekst: geen elektrische auto", "modellen": mods}
                        nieuw.append(regel); reg[url] = regel
                        print(f" overgeslagen  web {site['naam']:<8} {titel[:60]} (geen kWh)")
                        continue
                    if not mods:
                        regel |= {"status": "overgeslagen", "reden": "geen model van Plinkie in de titel", "modellen": []}
                        nieuw.append(regel); reg[url] = regel
                        print(f" overgeslagen  web {site['naam']:<8} {titel[:60]}")
                        continue
                else:
                    mods = []
                status, wat = haal_pagina(url, site, soort, mods, droog, html)
                regel |= {"status": status, "modellen": mods,
                          **({"bestand": wat} if status in ("opgehaald", "zou ophalen") else {"reden": wat})}
                opgehaald += status == "opgehaald"
            except Exception as e:
                regel |= {"status": "mislukt", "reden": str(e)[:300]}
            nieuw.append(regel); reg[url] = regel
            print(f"{regel['status']:>13}  web {site['naam']:<8} {', '.join(regel.get('modellen') or []) or '-':<24} {url[-60:]}")
            time.sleep(PAUZE_S)
    return nieuw
