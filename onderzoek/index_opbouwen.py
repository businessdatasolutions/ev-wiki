"""Bouwt wiki/index.md bij (CLAUDE.md §Process stap 7).

Bronnen: de bestaande regels blijven in hun volgorde staan; bronnen die er nog niet in staan, komen
als nieuw blok bovenaan, nieuwste publicatiedatum eerst. Zo blijft één blok gelijk aan één ingest in
log.md. Entiteiten, concepten, syntheses en threads: alfabetisch, met de eerste zin van de pagina.

    uv run --no-project --with pyyaml python onderzoek/index_opbouwen.py
"""
import glob
import re
from pathlib import Path

import yaml

WIKI = Path(__file__).resolve().parents[1] / "wiki"


def lees(f):
    s = open(f, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", s, re.S)
    return yaml.safe_load(m.group(1)), m.group(2)


def plat(t):
    t = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[\[([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    return t.replace("**", "")


def eerste_zin(body, kop=None):
    if kop and f"## {kop}" in body:
        body = body.split(f"## {kop}", 1)[1]
    regels = [l for l in body.split("\n") if l.strip() and not l.startswith(("#", ">", "|", "-", "**Plinkie"))]
    if not regels:
        return ""
    t = plat(regels[0])
    m = re.match(r"(.+?[.:])(\s|$)", t)
    return (m.group(1) if m else t)[:260]


def catalogus(map_, kop):
    items = []
    for f in glob.glob(f"{WIKI}/{map_}/*.md"):
        fm, body = lees(f)
        m = re.search(r"^# (.+)$", body, re.M)
        naam = m.group(1) if m else Path(f).stem
        na_kop = body.split(f"# {naam}", 1)[-1]
        soort = f" ({fm['kind']})" if fm.get("kind") else ""
        items.append((naam.lower(), f"- [[{Path(f).stem}|{naam}]]{soort} — {eerste_zin(na_kop)}"))
    return ["", f"## {kop}", ""] + ([r for _, r in sorted(items)] or ["Nog geen."])


def main():
    oud = (WIKI / "index.md").read_text(encoding="utf-8")
    bronsectie = oud.split("## Bronnen", 1)[1].split("\n## ", 1)[0] if "## Bronnen" in oud else ""
    bestaand = [l for l in bronsectie.split("\n") if l.startswith("- [[")]
    bekend = {re.match(r"- \[\[([^\]|]+)", l).group(1) for l in bestaand}
    bronnen = {Path(f).stem: lees(f) for f in glob.glob(f"{WIKI}/sources/*.md")}
    nieuw = sorted((b for b in bronnen if b not in bekend), reverse=True)
    regels = ["# Index", "",
              "De catalogus van elke pagina in deze wiki, bijgewerkt bij elke ingest. **Bronnen** per ingestbatch, "
              "nieuwste batch bovenaan; binnen een batch nieuwste publicatiedatum eerst. **Entiteiten, concepten, "
              "syntheses en threads** alfabetisch.", "", "## Bronnen", ""]
    for b in nieuw:
        fm, body = bronnen[b]
        auteur = (fm.get("author") or ["?"])[0]
        soort = " Vergelijkingstest." if fm.get("vergelijking") else ""
        regels.append(f"- [[{b}]] — *{fm['title']}* (**{auteur}**; {fm['date_published']}).{soort} {eerste_zin(body, 'Samenvatting')}")
    regels += [l for l in bestaand if re.match(r"- \[\[([^\]|]+)", l).group(1) in bronnen]
    regels += catalogus("entities", "Entiteiten") + catalogus("concepts", "Concepten")
    regels += catalogus("syntheses", "Syntheses") + catalogus("threads", "Threads") + [""]
    (WIKI / "index.md").write_text("\n".join(regels), encoding="utf-8")
    print(f"{len(nieuw)} nieuwe bron(nen) bovenaan, {len(bestaand)} bestaande behouden")


if __name__ == "__main__":
    main()
