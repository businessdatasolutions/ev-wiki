"""Voegt de concepten van de Process-agents samen in de wiki (CLAUDE.md §Parallel verwerken).

Leest elke ronde in onderzoek/verwerking/<map>/ (oordeel.json, voorstel.json, bron.md) en de
besluiten in onderzoek/verwerking/besluiten.yaml, en schrijft:

- de bronpagina, alleen als die nog niet bestaat (latere correcties in de wiki blijven staan);
- de modelpagina's, opnieuw opgebouwd uit **alle** rondes, behalve de handgeschreven pagina's;
- merk-, kanaal- en conceptpagina's, met hun bronnenlijst en tellingen.

Herhaalbaar: draait het twee keer zonder nieuwe ronde, dan verandert er niets.

    uv run --no-project --with pyyaml python onderzoek/samenvoegen.py [--sitemap] [--herschrijf-bronnen]

--sitemap haalt eerst de actuele modellenlijst van plinkie.nl op naar onderzoek/plinkie-modellen.txt.
Draai daarna onderzoek/index_opbouwen.py, de lint, scripts/quality-score.mjs en graph-export.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import urllib.request
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WIKI = REPO / "wiki"
VERWERKING = REPO / "onderzoek" / "verwerking"
MODELLEN_TXT = REPO / "onderzoek" / "plinkie-modellen.txt"
SECTIES = [("uitvoeringen", "Uitvoeringen"), ("fabrieksopgaven", "Fabrieksopgaven"), ("metingen", "Metingen"),
           ("valkuilen", "Valkuilen"), ("oordelen", "Oordelen")]


# ------------------------------------------------------------ hulp
def lees(p):
    s = open(p, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", s, re.S)
    return yaml.safe_load(m.group(1)), m.group(2)


def schrijf(p, fm, body):
    # quality_score en quality_notes schrijft scripts/quality-score.mjs. Die zoekt quality_notes op
    # één regel; als blok-lijst schreef hij er een tweede bij (dubbele sleutel, 06-10-2026).
    fm = dict(fm)
    kwaliteit = {k: fm.pop(k) for k in ("quality_score", "quality_notes") if k in fm}
    kop = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000).rstrip()
    for k, v in kwaliteit.items():
        # Precies zoals quality-score.mjs schrijft: enkele aanhalingstekens, '' voor een '
        kop += f"\n{k}: " + ("[" + ", ".join("'" + str(n).replace("'", "''") + "'" for n in v) + "]" if isinstance(v, list) else str(v))
    body = re.sub(r"\n{3,}", "\n\n", body.strip())
    tekst = "---\n" + kop + "\n---\n\n" + body + "\n"
    if not os.path.exists(p) or open(p, encoding="utf-8").read() != tekst:
        open(p, "w", encoding="utf-8").write(tekst)


def datum(x) -> str:
    return x.isoformat() if isinstance(x, dt.date) else str(x)


def conf(n, cap=None):
    c = round(min(0.95, 0.7 + 0.05 * max(n - 1, 0)), 2)
    return min(c, cap) if cap else c


def ververs_sitemap():
    with urllib.request.urlopen("https://plinkie.nl/sitemap.xml", timeout=30) as r:
        xml = r.read().decode("utf-8")
    paden = sorted(set(f"{a}/{b}" for a, b in re.findall(r"/deals/([a-z0-9-]+)/([a-z0-9-]+)</loc>", xml)))
    MODELLEN_TXT.write_text("\n".join(paden) + "\n", encoding="utf-8")
    print(len(paden), "modellen uit de sitemap van plinkie.nl")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sitemap", action="store_true", help="eerst de modellenlijst van plinkie.nl verversen")
    ap.add_argument("--herschrijf-bronnen", action="store_true", help="bronpagina's opnieuw uit het concept schrijven")
    args = ap.parse_args()
    if args.sitemap:
        ververs_sitemap()

    B = yaml.safe_load((VERWERKING / "besluiten.yaml").read_text(encoding="utf-8"))
    HAND = set(B.get("handgeschreven") or [])
    REMAP = B.get("uitvoering_van") or {}
    GEEN_CONCEPT = set(B.get("geen_concept") or [])
    CONCERN = B.get("concern") or {}
    NAAM_MERK = B.get("merknaam") or {}
    SITEMAP = set(MODELLEN_TXT.read_text().split())
    # Bronnen die dezelfde test zijn, tellen als één (een ANWB-video en de review erbij)
    TEST_VAN = {}
    for groep in B.get("zelfde_test") or []:
        for b in groep:
            TEST_VAN[b] = groep[0]

    def unieke_tests(bs):
        return len({TEST_VAN.get(b, b) for b in bs})

    def remap_tekst(s):
        for a, b in REMAP.items():
            s = re.sub(rf"\[\[(?:entities/)?{a}(\|[^\]]*)?\]\]", lambda m: f"[[{b}{m.group(1) or ''}]]", s)
            s = s.replace(a, b)
        for c in GEEN_CONCEPT:
            s = re.sub(rf"\[\[(?:concepts/)?{c}\|([^\]]*)\]\]", r"\1", s)
            s = re.sub(rf"\[\[(?:concepts/)?{c}\]\]", c, s)
        return s

    def remap(x):
        if isinstance(x, str):
            return REMAP.get(x, x)
        if isinstance(x, list):
            return [remap(i) for i in x]
        if isinstance(x, dict):  # ook sleutels: model_feiten is per model-slug
            return {REMAP.get(k, k): remap(v) for k, v in x.items()}
        return x

    # -------------------------------------------------------- 1. rondes en bronpagina's
    proces = []
    for d in sorted(VERWERKING.glob("*/")):
        o_pad, v_pad, b_pad = d / "oordeel.json", d / "voorstel.json", d / "bron.md"
        if not o_pad.exists():
            continue
        o = json.loads(o_pad.read_text())
        if not o.get("is_review") or not v_pad.exists() or not b_pad.exists():
            continue
        slug = o["bronpagina_bestand"][:-3]
        doel = WIKI / "sources" / f"{slug}.md"
        if not doel.exists() or args.herschrijf_bronnen:
            fm, body = lees(b_pad)
            fm = remap(fm)
            if d.name in (B.get("vergelijking") or []) or o.get("vergelijking"):
                fm["vergelijking"] = True
            schrijf(doel, fm, remap_tekst(body))
            print("bronpagina geschreven:", slug)
        proces.append({"naam": d.name, "slug": slug, "voorstel": remap(json.loads(v_pad.read_text()))})

    bronnen = {Path(f).stem: lees(f)[0] for f in glob.glob(f"{WIKI}/sources/*.md")}
    for p in proces:
        p["fm"] = bronnen[p["slug"]]

    def uitgever(fm):
        # Bij een artikel is author een persoon; het kanaal is de site (ANWB), net als bij video's
        return fm.get("site") or (fm.get("author") or ["?"])[0]

    def kanaal_kort(b):
        fm = bronnen[b]; d = datum(fm["date_published"])
        return f"{uitgever(fm)} {d[8:10]}-{d[5:7]}-{d[:4]}"

    def ingest(bs):
        return max((datum(bronnen[b].get("date_ingested") or bronnen[b]["date_published"]) for b in bs), default=None)

    def per_dag(b):
        fm = bronnen[b]; w = (fm.get("weergaven") or [{}])[-1]
        if not w.get("aantal"):
            return None
        d0 = dt.date.fromisoformat(datum(fm["date_published"])); d1 = dt.date.fromisoformat(datum(w["datum"]))
        return w["aantal"], d1.isoformat(), round(w["aantal"] / max((d1 - d0).days, 1))

    # -------------------------------------------------------- 2. entiteiten verzamelen
    bestaand = {Path(f).stem: lees(f) for f in glob.glob(f"{WIKI}/entities/*.md")}
    nieuw = {}
    for p in proces:
        for e in p["voorstel"].get("nieuwe_entiteiten", []):
            if e["slug"] not in REMAP:
                nieuw.setdefault(e["slug"], e)
    merken_bekend = {s for s, (fm, _) in bestaand.items() if fm.get("kind") == "merk"} | \
                    {s for s, e in nieuw.items() if e["kind"] == "merk"}

    def merk_van(slug):
        for bron in (bestaand.get(slug, ({}, ""))[0], nieuw.get(slug, {})):
            if bron.get("merk"):
                return bron["merk"]
        return max((m for m in merken_bekend if slug.startswith(m + "-")), key=len, default=slug.split("-")[0])

    def naam_van(slug):
        if slug in nieuw and nieuw[slug].get("naam"):
            return nieuw[slug]["naam"]
        if slug in bestaand:
            m = re.search(r"^# (.+)$", bestaand[slug][1], re.M)
            if m:
                return m.group(1)
        return NAAM_MERK.get(slug) or slug.replace("-", " ").title()

    modellen = set()
    claims = []  # (onderwerp, tegen, bron, tijd, grond)
    for b, fm in bronnen.items():
        modellen |= set(remap(fm.get("modellen") or []))
        for c in fm.get("concurrenten") or []:
            for t in c.get("tegen") or []:
                claims.append((remap(c["model"]), remap(t), b, str(c.get("tijd", "")), c.get("grond", "")))
    for c in claims:
        modellen |= {c[0], c[1]}
    feiten = {}
    for p in proces:
        for m, f in p["voorstel"].get("model_feiten", {}).items():
            modellen.add(m)
            for key, _ in SECTIES:
                for item in f.get(key) or []:
                    feiten.setdefault(m, {}).setdefault(key, []).append((remap_tekst(str(item)), p["slug"]))

    # -------------------------------------------------------- 3. modelpagina's
    geschreven = 0
    for m in sorted(modellen):
        if m in HAND:
            continue
        merk = merk_van(m)
        eigen = sorted(b for b, fm in bronnen.items() if m in remap(fm.get("modellen") or []))
        genoemd = {c[2] for c in claims if m in (c[0], c[1])} | {b for items in feiten.get(m, {}).values() for _, b in items}
        alle = sorted(set(eigen) | genoemd)
        rest = m[len(merk) + 1:] if m.startswith(merk + "-") else m
        pad = f"/deals/{merk}/{rest}" if f"{merk}/{rest}" in SITEMAP else ""
        naam = naam_van(m)
        aliases = [naam] + [a for a in (nieuw.get(m, {}).get("aliases") or []) if a != naam]
        if m in bestaand:
            aliases += [a for a in (bestaand[m][0].get("aliases") or []) if a not in aliases]
        eigen_claims = [c for c in claims if c[0] == m]
        rel = [{"type": "part-of", "target": merk}]
        per_tegen = {}
        for (_, t, b, tijd, grond) in eigen_claims:
            per_tegen.setdefault(t, []).append(f"{kanaal_kort(b)} ({tijd}): {grond}".strip())
        rel += [{"type": "competes-with", "target": t, "via": "; ".join(dict.fromkeys(v))} for t, v in per_tegen.items()]
        cap = 0.75 if unieke_tests(eigen) < 2 else None
        dag = ingest(alle) or datum(dt.date.today())
        fm = {"type": "entity", "kind": "model", "merk": merk, "plinkie_pad": pad, "aliases": list(dict.fromkeys(aliases)),
              "tags": [merk], "confidence": conf(unieke_tests(alle), cap), "last_confirmed": dag, "accessed_at": dag,
              "source_count": unieke_tests(alle), "relationships": rel}
        merknaam = NAAM_MERK.get(merk) or naam_van(merk)
        L = [f"# {naam}", ""]
        if eigen:
            L.append(f"Model van [[{merk}|{merknaam}]]. Bronnen over dit model: "
                     + ", ".join(f"[[{b}|{kanaal_kort(b)}]]" for b in eigen) + ".")
            if cap:
                L.append("Met één eigen bron (of één test, ook als die in video en artikel verscheen) blijft de zekerheid op hooguit 0,75.")
        else:
            L.append(f"Model van [[{merk}|{merknaam}]]. Deze wiki heeft nog geen review van de {naam} zelf; "
                     "de pagina bestaat omdat een bron hem als concurrent noemt of er iets over zegt.")
        L += ["", f"**Plinkie.** `{pad}`, staat in de sitemap van plinkie.nl." if pad
              else "**Plinkie.** Staat niet in de sitemap van plinkie.nl.", ""]
        for key, kop in SECTIES:
            items = feiten.get(m, {}).get(key)
            if items:
                L += [f"## {kop}", ""] + [f"- {t} ([[{b}|{kanaal_kort(b)}]])" for t, b in items] + [""]
        inkomend = [c for c in claims if c[1] == m]
        if eigen_claims or inkomend:
            L += ["## Concurrenten", ""]
            if eigen_claims:
                L += ["| Tegen | Bron | Tijd | Grond |", "| --- | --- | --- | --- |"]
                L += [f"| [[{t}|{naam_van(t)}]] | [[{b}|{kanaal_kort(b)}]] | {tijd} | {grond} |" for (_, t, b, tijd, grond) in eigen_claims] + [""]
            if inkomend:
                L += ["Genoemd als concurrent van:", "", "| Model | Bron | Tijd | Grond |", "| --- | --- | --- | --- |"]
                L += [f"| [[{o}|{naam_van(o)}]] | [[{b}|{kanaal_kort(b)}]] | {tijd} | {grond} |" for (o, _, b, tijd, grond) in inkomend] + [""]
        w = [(b, per_dag(b)) for b in eigen if per_dag(b)]
        if w:
            L += ["## Weergaven", "", "| Bron | Gemeten | Aantal | Per dag |", "| --- | --- | --- | --- |"]
            L += [f"| [[{b}|{kanaal_kort(b)}]] | {d} | {a} | {pd} |" for b, (a, d, pd) in w] + [""]
        deb = []
        for p in proces:
            for r in p["voorstel"].get("relaties_met_bestaande_bronnen", []):
                if r.get("type") == "contradicts" and m in remap(p["fm"].get("modellen") or []) and r["target"] in bronnen:
                    deb.append(f"- {r.get('via')} ([[{p['slug']}|{kanaal_kort(p['slug'])}]] tegen "
                               f"[[{r['target']}|{kanaal_kort(r['target'])}]])")
        L += ["## Debatten en vervanging", ""] + (deb or ["Nog geen tegenspraak vastgelegd."])
        schrijf(WIKI / "entities" / f"{m}.md", fm, "\n".join(L))
        geschreven += 1
    print(geschreven, "modelpagina's")

    # -------------------------------------------------------- 4. merken
    per_merk = {}
    for m in modellen:
        per_merk.setdefault(merk_van(m), set()).add(m)
    merk_feiten = {}
    for p in proces:
        for mk, items in (p["voorstel"].get("merk_feiten") or {}).items():
            merk_feiten.setdefault(mk, []).extend((remap_tekst(str(i)), p["slug"]) for i in items)
    for mk in sorted(merken_bekend | set(per_merk)):
        if mk in modellen:
            continue
        mods = sorted(per_merk.get(mk, []))
        srcs = sorted({b for b, fm in bronnen.items() if mk in (fm.get("merken") or [])} |
                      {c[2] for c in claims if c[0] in mods or c[1] in mods} | {b for _, b in merk_feiten.get(mk, [])})
        if mk in bestaand:
            fm, body = bestaand[mk]
            intro = body.split("## Modellen in deze wiki")[0].strip()
        else:
            fm = {"type": "entity", "kind": "merk", "aliases": [NAAM_MERK.get(mk, naam_van(mk))], "tags": [mk]}
            intro = f"# {NAAM_MERK.get(mk, naam_van(mk))}\n\n{remap_tekst((nieuw.get(mk) or {}).get('tekst') or 'Automerk.')}"
        concern = CONCERN.get(mk)
        if concern and f"[[{concern}" not in intro:
            intro += f"\n\nHoort bij [[{concern}]]."
        dag = ingest(srcs) or fm.get("last_confirmed")
        fm.update({"confidence": conf(len(srcs)), "last_confirmed": dag, "accessed_at": dag, "source_count": len(srcs)})
        fm.pop("relationships", None)
        if concern:
            fm["relationships"] = [{"type": "part-of", "target": concern}]
        L = [intro, "", "## Modellen in deze wiki", "", ", ".join(f"[[{m}|{naam_van(m)}]]" for m in mods) or "Nog geen.", ""]
        if merk_feiten.get(mk):
            L += ["## Uit de bronnen", ""] + [f"- {t} ([[{b}|{kanaal_kort(b)}]])" for t, b in merk_feiten[mk]] + [""]
        L += ["## Bronnen", ""] + [f"- [[{b}|{kanaal_kort(b)}]]" for b in srcs] + ["", "## Debatten en vervanging", "", "Nog geen tegenspraak."]
        schrijf(WIKI / "entities" / f"{mk}.md", fm, "\n".join(L))

    # -------------------------------------------------------- 5. kanalen, aanbieders, concerns
    kanalen = {s: fm for s, (fm, _) in bestaand.items() if fm.get("kind") == "kanaal"}
    for s, e in nieuw.items():
        if e.get("kind") == "kanaal" and s not in kanalen and not (WIKI / "entities" / f"{s}.md").exists():
            schrijf(WIKI / "entities" / f"{s}.md",
                    {"type": "entity", "kind": "kanaal", "aliases": [e.get("naam") or s], "tags": [s], "confidence": 0.7,
                     "last_confirmed": datum(dt.date.today()), "accessed_at": datum(dt.date.today()), "source_count": 1},
                    f"# {e.get('naam') or s}\n\n{e.get('tekst') or 'Kanaal.'}\n\n## Bronnen\n\n\n## Debatten en vervanging\n\nNog geen tegenspraak.")
            kanalen[s] = lees(WIKI / "entities" / f"{s}.md")[0]
    bijwerken = list(kanalen) + [s for s, (fm, _) in bestaand.items() if fm.get("kind") == "aanbieder"] + sorted(set(CONCERN.values()))
    for slug in bijwerken:
        f = WIKI / "entities" / f"{slug}.md"
        if not f.exists():
            continue
        fm, body = lees(f)
        if fm.get("kind") == "kanaal":
            naam = (fm.get("aliases") or [slug])[0]
            srcs = sorted(b for b, bf in bronnen.items() if uitgever(bf) == naam)
        elif fm.get("kind") == "aanbieder":
            ouder = next((r["target"] for r in fm.get("relationships") or [] if r["type"] == "part-of"), None)
            naam = (kanalen.get(ouder, {}).get("aliases") or [None])[0]
            srcs = sorted(b for b, bf in bronnen.items() if naam and uitgever(bf) == naam)
        else:
            leden = {k for k, v in CONCERN.items() if v == slug}
            srcs = sorted({b for b, bf in bronnen.items() if leden & set(bf.get("merken") or [])})
        if not srcs:
            continue
        deel = re.split(r"\n## Bronnen\n", body)[0].rstrip()
        rest = body.split("## Debatten en vervanging")[-1] if "## Debatten en vervanging" in body else "\n\nNog geen tegenspraak."
        body = deel + "\n\n## Bronnen\n\n" + "\n".join(f"- [[{b}|{kanaal_kort(b)}]]" for b in srcs) + "\n\n## Debatten en vervanging" + rest
        cap = 0.75 if (fm.get("ook_aanbieder") or fm.get("kind") == "aanbieder") else None
        dag = ingest(srcs)
        fm.update({"source_count": len(srcs), "confidence": conf(len(srcs), cap), "last_confirmed": dag, "accessed_at": dag})
        schrijf(f, fm, body)

    # -------------------------------------------------------- 6. concepten
    aanvulling = {}
    for p in proces:
        for c in p["voorstel"].get("concepten", []):
            if c["slug"] not in GEEN_CONCEPT and c.get("toevoeging"):
                aanvulling.setdefault(c["slug"], []).append((remap_tekst(c["toevoeging"]), p["slug"]))
    for slug, items in aanvulling.items():
        f = WIKI / "concepts" / f"{slug}.md"
        if not f.exists():
            nc = (B.get("nieuwe_concepten") or {}).get(slug)
            if not nc:
                print("concept zonder pagina en zonder besluit, overgeslagen:", slug)
                continue
            schrijf(f, {"type": "concept", "aliases": [nc["naam"]], "tags": [slug], "confidence": 0.7,
                        "last_confirmed": ingest([b for _, b in items]), "accessed_at": ingest([b for _, b in items]), "source_count": 0},
                    f"# {nc['naam']}\n\n{nc['definitie']}\n\n## Bronnen\n\n\n## Debatten en vervanging\n\nNog geen tegenspraak.")
        fm, body = lees(f)
        body = re.sub(r"\n## Uit de bronnen( van [0-9-]+)?\n.*?(?=\n## )", "", body, flags=re.S)
        blok = "\n## Uit de bronnen\n\n" + "\n".join(f"- {t} ([[{b}|{kanaal_kort(b)}]])" for t, b in items) + "\n"
        i = body.index("\n## Bronnen")
        body = body[:i] + "\n" + blok + body[i:]
        oude = re.findall(r"^- \[\[([^\]|]+)", body.split("## Bronnen\n")[1].split("## Debatten")[0], re.M)
        srcs = list(dict.fromkeys(oude + [b for _, b in items]))
        body = re.sub(r"(## Bronnen\n\n).*?(\n## Debatten)",
                      lambda mm: mm.group(1) + "\n".join(f"- [[{b}|{kanaal_kort(b)}]]" for b in srcs) + "\n" + mm.group(2), body, flags=re.S)
        dag = ingest(srcs)
        fm.update({"source_count": len(srcs), "confidence": max(fm.get("confidence", 0.7), conf(len(srcs))),
                   "last_confirmed": dag, "accessed_at": dag})
        if len(srcs) > 1 and "## Debatten en vervanging" not in body:
            body += "\n## Debatten en vervanging\n\nNog geen tegenspraak.\n"
        schrijf(f, fm, body)

    # -------------------------------------------------------- 7. gebroken links
    alle = {Path(f).stem for f in glob.glob(f"{WIKI}/**/*.md", recursive=True)}
    kapot = {}
    for f in glob.glob(f"{WIKI}/**/*.md", recursive=True):
        if f.endswith("index.md"):
            continue
        for l in re.findall(r"\[\[([^\]|#]+)", open(f, encoding="utf-8").read()):
            t = l.split("/")[-1]
            if t not in alle and not l.startswith("assets"):
                kapot.setdefault(t, set()).add(Path(f).name)
    print("gebroken links:", {k: sorted(v)[:3] for k, v in kapot.items()} or "geen")


if __name__ == "__main__":
    main()
