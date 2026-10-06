"""De verzamelaar: haalt zelfstandig reviews van elektrische auto's op naar raw/.

Dit is Acquire uit CLAUDE.md, geautomatiseerd. De verzamelaar schrijft alleen in raw/ en
onderzoek/, nooit in wiki/ (behalve een logregel `acquire`). Wiki-pagina's schrijven blijft
Process, met een mens erbij.

Twee soorten runs:

- **Gewone run.** Leest de nieuwste uploads van elk vast kanaal (onderzoek/kanalen.yaml),
  koppelt titels aan de modellen in de sitemap van plinkie.nl, en haalt elke treffer op met
  de transcript-skill (`--sub-lang` in de taal van het kanaal).
- **Verkenning** (hooguit eens per VERKEN_DAGEN dagen, of met --verken). Zoekt op YouTube
  naar reviews van een wisselend deel van de modellen. Treffers van kanalen buiten de lijst
  worden niet opgehaald maar als voorstel geschreven naar onderzoek/kanaalvoorstellen.md.

Alles wat de verzamelaar ziet, staat in onderzoek/register.jsonl, ook wat hij oversloeg.
Daar leest hij ook uit wat al gezien is.

    uv run --no-project --with-requirements .claude/skills/youtube-transcript-skill/requirements.txt \\
        python onderzoek/verzamelaar.py [--droog] [--verken] [--max N]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

import yaml
import yt_dlp

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[1]
ONDERZOEK = REPO / "onderzoek"
RAW_VIDEOS = REPO / "raw" / "videos"
SKILL = REPO / ".claude" / "skills" / "youtube-transcript-skill"
REGISTER = ONDERZOEK / "register.jsonl"
STAAT = ONDERZOEK / "staat.json"
VOORSTELLEN = ONDERZOEK / "kanaalvoorstellen.md"
LOG = REPO / "wiki" / "log.md"

SITEMAP = "https://plinkie.nl/sitemap.xml"
MIN_DUUR_S = 240          # korter is een short of een teaser, geen review
VERKEN_DAGEN = 7
VERKEN_MODELLEN = 15      # modellen per verkenning; de rest volgt bij de volgende
PAUZE_S = 2.0             # tussen twee lijst- of zoekverzoeken aan YouTube
PAUZE_OPHALEN_S = 15.0    # tussen twee transcripts: na een reeks geeft YouTube HTTP 429
MAX_POGINGEN = 3          # daarna blijft een mislukte video in het register staan
MERKNAAM = {"vw": "volkswagen"}
ALGEMENE_ACHTERVOEGSELS = {"limousine", "electric", "elektrisch", "suv", "hatchback", "sedan", "e", "tech",
                           "sportback", "tourer", "estate", "coupe", "shooting", "brake"}


# ---------------------------------------------------------------- tekst

def plat(tekst: str) -> str:
    t = unicodedata.normalize("NFD", tekst)
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def woorden(tekst: str) -> list[str]:
    # "+" is een woord: Plinkie schrijft Toyota C-HR+ als c-hr-plus (06-10-2026)
    return [w for w in re.split(r"[^a-z0-9]+", plat(tekst).replace("+", " plus ")) if w]


def slugify(tekst: str) -> str:
    return "-".join(woorden(tekst))[:90].strip("-")


# ---------------------------------------------------------------- modellen

def modellen_van_plinkie() -> list[dict]:
    """De modellen die Plinkie toont, uit de openbare sitemap: /deals/<merk>/<model>."""
    with urllib.request.urlopen(SITEMAP, timeout=30) as r:
        xml = r.read().decode("utf-8")
    paden = sorted(set(re.findall(r"/deals/([a-z0-9-]+)/([a-z0-9-]+)</loc>", xml)))
    out = []
    for merk, model in paden:
        out.append({
            "pad": f"/deals/{merk}/{model}",
            "sleutel": f"{merk}/{model}",
            "merk_woorden": merk.split("-"),
            "model_woorden": model.split("-"),
            "naam": f"{merk.replace('-', ' ')} {model.replace('-', ' ')}",
        })
    return out


def _bevat_reeks(ws: list[str], reeks: list[str]) -> bool:
    n = len(reeks)
    return any(ws[i:i + n] == reeks for i in range(len(ws) - n + 1))


def modellen_in(titel: str, modellen: list[dict]) -> list[str]:
    """Welke modellen noemt deze titel? Merk én model moeten erin staan.

    Het model als woordreeks ("id polo") of aaneengeschreven ("idpolo", "ec3" voor ë-C3).
    Een model van één teken (Renault "4", "5") telt alleen direct na het merk, anders is
    elke "4x4" of "5 jaar" een treffer.
    """
    ws = []
    for i, w in enumerate(woorden(titel)):
        ws.append(MERKNAAM.get(w, w))
        # "Mercedes C-Klasse" is mercedes-benz in de sitemap (ANWB, 06-10-2026)
        if w == "mercedes" and (woorden(titel)[i + 1:i + 2] or [""])[0] != "benz":
            ws.append("benz")
    vast = "".join(ws)

    def past(mw: list[str], merk: list[str]) -> bool:
        if len(mw) == 1 and len(mw[0]) == 1:
            return _bevat_reeks(ws, merk + mw)
        return _bevat_reeks(ws, mw) or (len(mw) > 1 and "".join(mw) in vast) or ("".join(mw) in ws)

    treffers = []
    for m in modellen:
        if _bevat_reeks(ws, m["merk_woorden"]) and past(m["model_woorden"], m["merk_woorden"]):
            treffers.append(m["sleutel"])
    # Tweede ronde, alleen voor een merk zonder treffer: algemene woorden aan het eind van de
    # Plinkie-naam mogen ontbreken ("C-Klasse" is c-klasse-limousine, "Kona" is kona-electric).
    # Een benzineversie koppelt dan ook; webbronnen.py haalt een review daarom alleen op als de
    # tekst "kWh" noemt, en Process controleert of het om de elektrische auto gaat.
    merken_met_treffer = {t.split("/")[0] for t in treffers}
    for m in modellen:
        if m["sleutel"].split("/")[0] in merken_met_treffer or not _bevat_reeks(ws, m["merk_woorden"]):
            continue
        kern = list(m["model_woorden"])
        while len(kern) > 1 and kern[-1] in ALGEMENE_ACHTERVOEGSELS:
            kern.pop()
        if kern != m["model_woorden"] and past(kern, m["merk_woorden"]):
            treffers.append(m["sleutel"])
    # Een treffer die binnen een andere treffer van hetzelfde merk valt, is die andere:
    # "Audi Q4 e-tron" is niet ook "audi/e-tron", "Renault 4 E-Tech" niet ook "renault/4".
    def binnen(kort: str, lang: str) -> bool:
        (mk, mo_k), (ml, mo_l) = kort.split("/"), lang.split("/")
        return mk == ml and kort != lang and _bevat_reeks(mo_l.split("-"), mo_k.split("-"))
    return [t for t in treffers if not any(binnen(t, o) for o in treffers)]


# ---------------------------------------------------------------- register

def lees_register() -> dict[str, dict]:
    """De laatste regel per video, met het aantal mislukte pogingen erbij."""
    reg, mislukt = {}, {}
    if REGISTER.exists():
        for regel in REGISTER.read_text(encoding="utf-8").splitlines():
            if regel.strip():
                e = json.loads(regel)
                reg[e["video_id"]] = e
                if e.get("status") == "mislukt":
                    mislukt[e["video_id"]] = mislukt.get(e["video_id"], 0) + 1
    for vid, n in mislukt.items():
        reg[vid]["pogingen"] = n
    return reg


def klaar_mee(e: dict | None) -> bool:
    """Is deze video afgehandeld? Een mislukte poging krijgt een herkansing."""
    return e is not None and not (e.get("status") == "mislukt" and e.get("pogingen", 1) < MAX_POGINGEN)


def al_in_raw() -> set[str]:
    ids = set()
    for f in RAW_VIDEOS.glob("*.md"):
        m = re.search(r"^video_id: ['\"]?([\w-]{11})", f.read_text(encoding="utf-8"), re.M)
        if m:
            ids.add(m.group(1))
    return ids


def registreer(regels: list[dict]) -> None:
    with REGISTER.open("a", encoding="utf-8") as f:
        for e in regels:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def lees_staat() -> dict:
    return json.loads(STAAT.read_text()) if STAAT.exists() else {"laatste_verkenning": None, "rotatie": 0}


# ---------------------------------------------------------------- YouTube

def ydl(taal: str | None = None) -> yt_dlp.YoutubeDL:
    opts = {"extract_flat": True, "quiet": True, "no_warnings": True, "skip_download": True}
    if taal:
        opts["extractor_args"] = {"youtube": {"lang": [taal]}}
    return yt_dlp.YoutubeDL(opts)


def uploads(kanaal: dict) -> list[dict]:
    with ydl(kanaal.get("taal")) as y:
        y.params["playlistend"] = int(kanaal.get("uploads", 40))
        info = y.extract_info(kanaal["url"], download=False)
    return [e for e in info.get("entries") or [] if e.get("id")]


def zoek(vraag: str, n: int = 10, taal: str = "nl") -> list[dict]:
    with ydl(taal) as y:
        info = y.extract_info(f"ytsearch{n}:{vraag}", download=False)
    return [e for e in info.get("entries") or [] if e.get("id")]


def haal_op(video_id: str, taal: str, pad: Path, modellen: list[str], kanaal: str) -> tuple[bool, str, bool]:
    """Transcript ophalen met de skill, en vastleggen dat de verzamelaar het deed."""
    cmd = [sys.executable, str(SKILL / "fetch_transcript.py"), f"https://www.youtube.com/watch?v={video_id}",
           "--sub-lang", taal, "--timeout", "60000", "-o", str(pad)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=SKILL)
    geblokkeerd = "HTTP Error 429" in r.stderr
    if r.returncode != 0 or not pad.exists():
        uitvoer = (r.stderr or r.stdout).strip().splitlines()
        return False, ("HTTP 429; " if geblokkeerd else "") + (uitvoer[-1] if uitvoer else "onbekende fout"), geblokkeerd
    tekst = pad.read_text(encoding="utf-8")
    blok = yaml.safe_dump({"verzameld": {
        "door": "verzamelaar",
        "datum": dt.date.today().isoformat(),
        "kanaal": kanaal,
        "modellen_kandidaat": modellen,
        "status": "wacht op Process",
    }}, allow_unicode=True, sort_keys=False).rstrip()
    # Achter de frontmatter van de skill, vóór de afsluitende ---
    kop_einde = tekst.index("\n---", 4)
    pad.write_text(tekst[:kop_einde] + "\n" + blok + tekst[kop_einde:], encoding="utf-8")
    return True, "", geblokkeerd


# ---------------------------------------------------------------- runs

def gewone_run(kanalen: list[dict], modellen: list[dict], reg: dict, in_raw: set, max_ophalen: int, droog: bool) -> list[dict]:
    nieuw, opgehaald, geblokkeerd = [], 0, False
    vandaag = dt.date.today().isoformat()
    for k in kanalen:
        try:
            lijst = uploads(k)
        except Exception as e:  # een kanaal dat faalt, houdt de rest niet tegen
            print(f"! {k['naam']}: {e}", file=sys.stderr)
            continue
        time.sleep(PAUZE_S)
        for e in lijst:
            vid = e["id"]
            if klaar_mee(reg.get(vid)) or vid in in_raw:
                continue
            titel = e.get("title") or ""
            mods = modellen_in(titel, modellen)
            duur = e.get("duration") or 0
            regel = {"video_id": vid, "titel": titel, "kanaal": k["naam"], "lijst": "vast", "modellen": mods,
                     "duur_s": duur, "weergaven_circa": e.get("view_count"), "gezien": vandaag}
            uitsluiten = k.get("uitsluiten")
            if not mods:
                regel |= {"status": "overgeslagen", "reden": "geen model van Plinkie in de titel"}
            elif uitsluiten and re.search(uitsluiten, titel, re.I):
                regel |= {"status": "overgeslagen", "reden": f"titel valt onder uitsluiten: {uitsluiten}"}
            elif duur and duur < MIN_DUUR_S:
                regel |= {"status": "overgeslagen", "reden": f"korter dan {MIN_DUUR_S} s"}
            elif opgehaald >= max_ophalen or geblokkeerd:
                continue  # niet registreren: de volgende run pakt hem op
            elif droog:
                regel |= {"status": "zou ophalen"}
            else:
                pad = RAW_VIDEOS / f"{slugify(titel) or vid}.md"
                if pad.exists():
                    pad = RAW_VIDEOS / f"{slugify(titel)}-{vid}.md"
                ok, fout, blok = haal_op(vid, k.get("taal", "nl"), pad, mods, k["naam"])
                if blok and not ok:
                    # YouTube weigert deze verbinding: doorgaan verlengt de blokkade.
                    geblokkeerd = True
                    print("! HTTP 429: deze run haalt niets meer op", file=sys.stderr)
                if ok:
                    regel |= {"status": "opgehaald", "bestand": str(pad.relative_to(REPO))}
                else:
                    # Een bestand met alleen metadata zou de video bij de volgende run als
                    # "al in raw/" laten overslaan; weg ermee, het register onthoudt de poging.
                    pad.unlink(missing_ok=True)
                    regel |= {"status": "mislukt", "reden": fout[:300]}
                opgehaald += ok
                time.sleep(PAUZE_OPHALEN_S)
            nieuw.append(regel)
            print(f"{regel['status']:>13}  {k['naam']:<10} {', '.join(mods) or '-':<24} {titel[:60]}")
    return nieuw


def verkenning(kanalen: dict, modellen: list[dict], reg: dict, staat: dict, droog: bool) -> list[dict]:
    vast = {k["naam"].lower() for k in kanalen["vast"]}
    genegeerd = {(g["naam"] if isinstance(g, dict) else g).lower() for g in kanalen.get("genegeerd") or []}
    start = staat.get("rotatie", 0) % max(len(modellen), 1)
    beurt = (modellen[start:] + modellen[:start])[:VERKEN_MODELLEN]
    vandaag = dt.date.today().isoformat()
    nieuw = []
    for m in beurt:
        for taal, vraag in (("nl", f"{m['naam']} review"), ("nl", f"{m['naam']} test"), ("en", f"{m['naam']} review")):
            try:
                hits = zoek(vraag, 10, taal)
            except Exception as e:
                print(f"! zoeken '{vraag}': {e}", file=sys.stderr)
                continue
            time.sleep(PAUZE_S)
            for e in hits:
                kanaal = e.get("channel") or e.get("uploader") or "?"
                if kanaal.lower() in vast or kanaal.lower() in genegeerd or klaar_mee(reg.get(e["id"])):
                    continue
                mods = modellen_in(e.get("title") or "", modellen)
                if m["sleutel"] not in mods or (e.get("duration") or 0) < MIN_DUUR_S:
                    continue
                regel = {"video_id": e["id"], "titel": e.get("title"), "kanaal": kanaal,
                         "kanaal_url": e.get("channel_url"), "lijst": "verkenning", "modellen": mods,
                         "duur_s": e.get("duration"), "weergaven_circa": e.get("view_count"),
                         "zoekvraag": vraag, "gezien": vandaag, "status": "voorstel"}
                reg[e["id"]] = regel
                nieuw.append(regel)
    staat["rotatie"] = start + len(beurt)
    staat["laatste_verkenning"] = vandaag
    if not droog:
        STAAT.write_text(json.dumps(staat, indent=2) + "\n")
    print(f"verkenning: {len(beurt)} modellen ({beurt[0]['sleutel']} … {beurt[-1]['sleutel']}), {len(nieuw)} kandidaten buiten de lijst")
    return nieuw


def schrijf_voorstellen(reg: dict, kanalen: dict) -> None:
    """Alle voorstellen uit het register, per kanaal opgeteld. Wordt elke keer opnieuw opgebouwd."""
    vast = {k["naam"].lower() for k in kanalen["vast"]}
    genegeerd = {(g["naam"] if isinstance(g, dict) else g).lower() for g in kanalen.get("genegeerd") or []}
    per = {}
    for e in reg.values():
        if e.get("status") != "voorstel" or e["kanaal"].lower() in vast | genegeerd:
            continue
        p = per.setdefault(e["kanaal"], {"url": e.get("kanaal_url"), "video": [], "modellen": set(), "weergaven": 0})
        p["video"].append(e)
        p["modellen"].update(e["modellen"])
        p["weergaven"] += e.get("weergaven_circa") or 0
    rij = sorted(per.items(), key=lambda kv: (-len(kv[1]["modellen"]), -kv[1]["weergaven"]))
    regels = [
        "# Kanaalvoorstellen",
        "",
        "Kanalen buiten `kanalen.yaml` die de verzamelaar bij een verkenning vond, met reviews van modellen",
        "uit de sitemap van Plinkie. **Er is niets van opgehaald.** Neem een kanaal over in `vast:` om het",
        "voortaan te verzamelen, of in `genegeerd:` (met reden) om het niet meer te zien.",
        "",
        f"Opgebouwd uit `register.jsonl` op {dt.date.today().isoformat()}. Weergaven zijn afgerond.",
        "",
        "| Kanaal | Modellen | Video's | Weergaven (circa) | Voorbeelden |",
        "| --- | --- | --- | --- | --- |",
    ]
    for naam, p in rij:
        vb = "<br>".join(f"[{(v['titel'] or '')[:50]}](https://www.youtube.com/watch?v={v['video_id']})" for v in p["video"][:3])
        kanaal = f"[{naam}]({p['url']})" if p["url"] else naam
        mods = ", ".join(sorted(p["modellen"]))[:80]
        regels.append(f"| {kanaal} | {len(p['modellen'])}: {mods} | {len(p['video'])} | {p['weergaven']} | {vb} |")
    if not rij:
        regels.append("| – | – | – | – | Nog geen voorstellen. |")
    VOORSTELLEN.write_text("\n".join(regels) + "\n", encoding="utf-8")


def log_acquire(opgehaald: list[dict]) -> None:
    if not opgehaald:
        return
    vandaag = dt.date.today().isoformat()
    lijst = "\n".join(f"- `{e['bestand']}` ({e['kanaal']}; {', '.join(e.get('modellen') or []) or 'artikel'})" for e in opgehaald)
    regel = (f"## [{vandaag}] acquire | verzamelaar: {len(opgehaald)} review(s)\n\n"
             f"Opgehaald door `onderzoek/verzamelaar.py`, nog niet verwerkt (wacht op Process):\n\n{lijst}\n\n")
    tekst = LOG.read_text(encoding="utf-8")
    i = tekst.index("\n---\n") + len("\n---\n")
    LOG.write_text(tekst[:i] + "\n" + regel + tekst[i:].lstrip("\n"), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--droog", action="store_true", help="niets ophalen en niets schrijven; laat zien wat er zou gebeuren")
    ap.add_argument("--verken", action="store_true", help="verkenning nu, ook als de vorige korter dan een week geleden was")
    ap.add_argument("--geen-verkenning", action="store_true")
    ap.add_argument("--geen-web", action="store_true", help="de webbronnen (reviews, artikelen) overslaan")
    ap.add_argument("--max", type=int, default=8, help="hoeveel transcripts hooguit per run (standaard 8)")
    args = ap.parse_args()

    kanalen = yaml.safe_load((ONDERZOEK / "kanalen.yaml").read_text(encoding="utf-8"))
    modellen = modellen_van_plinkie()
    reg, in_raw, staat = lees_register(), al_in_raw(), lees_staat()
    print(f"{len(modellen)} modellen uit de sitemap van Plinkie, {len(reg)} video's in het register, {len(in_raw)} in raw/")

    nieuw = gewone_run(kanalen["vast"], modellen, reg, in_raw, args.max, args.droog)
    for e in nieuw:
        reg[e["video_id"]] = e

    laatste = staat.get("laatste_verkenning")
    verkennen_web = args.verken or (not args.geen_verkenning and (
        laatste is None or (dt.date.today() - dt.date.fromisoformat(laatste)).days >= VERKEN_DAGEN))
    if kanalen.get("web") and not args.geen_web:
        import webbronnen
        nieuw += webbronnen.web_run(kanalen["web"], modellen, modellen_in, reg, args.max, verkennen_web, args.droog)
    verkennen = args.verken or (not args.geen_verkenning and (
        laatste is None or (dt.date.today() - dt.date.fromisoformat(laatste)).days >= VERKEN_DAGEN))
    if verkennen:
        nieuw += verkenning(kanalen, modellen, reg, staat, args.droog)

    if args.droog:
        print("droog: niets geschreven")
        return 0
    registreer(nieuw)
    schrijf_voorstellen(lees_register(), kanalen)
    log_acquire([e for e in nieuw if e.get("status") == "opgehaald"])
    tel = {s: sum(e.get("status") == s for e in nieuw) for s in ("opgehaald", "mislukt", "overgeslagen", "voorstel")}
    print("klaar:", ", ".join(f"{v} {k}" for k, v in tel.items()))
    return 1 if tel["mislukt"] and not tel["opgehaald"] else 0


if __name__ == "__main__":
    sys.exit(main())
