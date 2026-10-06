# Opdracht voor een Process-agent

Sjabloon voor de subagents bij parallel verwerken (CLAUDE.md §Parallel verwerken). Vul `{BRON}`
(pad van het ruwe bestand), `{MAP}` (naam van de verwerkingsmap, kort en zonder datum) en eventueel
`{AANWIJZING}` (wat je over deze bron al weet of vermoedt) in, en geef de tekst hieronder als prompt.
Gebruikt op 06-10-2026 voor de tweede ingest (negen agents tegelijk).

---

Je verwerkt één ruwe bron tot een concept voor een LLM-wiki over elektrische auto's (repo
`/Users/witoldtenhove/Documents/Projects/ev-wiki`). Je schrijft **niets** in `wiki/` of `raw/`: alleen
in je eigen uitvoermap. Een andere stap voegt jouw concept later samen met dat van andere agents.

**Je bron:** `{BRON}`
**Je uitvoermap:** `/Users/witoldtenhove/Documents/Projects/ev-wiki/onderzoek/verwerking/{MAP}/`
{AANWIJZING}

## Lees eerst
1. `CLAUDE.md`, vooral: "Bronnen controleren vóór ingest" (videocontract, veldmapping, **Getallen uit
   spraakherkenning**), "Werkprincipes", "EV-lens" (merken, modellen, feitsoorten, weergaven,
   modelpagina's, **Concurrentie**, inclusief "een vergelijking is automatisch concurrentie"),
   "Verzamelaar" (bij Process van een verzamelde video), "Levenscyclus".
2. Precedenten: `wiki/sources/2024-11-15-chinese-evs-onder-de-25-mille-kleine-autos-grote-verleiding.md`
   (vergelijkingstest) en `wiki/sources/2026-09-13-skoda-epiq-troeft-zelfs-volkswagen-id-polo-af.md` (rijtest).
3. Bestaande pagina's: `ls wiki/entities/ wiki/concepts/`; lees de pagina's van de modellen en merken
   waar je bron over gaat.
4. De modellen van Plinkie: `onderzoek/plinkie-modellen.txt` (`merk/model` = pad `/deals/<merk>/<model>`).
5. De besluiten van eerdere rondes: `onderzoek/verwerking/besluiten.yaml`.

## Doen
**Stap 0, controle.** Lees de hele bron. Stel vast: de taal (geen `transcript_track` in de kop betekent
browserpaneel, dus mogelijk een andere taal); of het een review, test of vergelijking is, of iets anders
(nieuws, occasionverhaal, pechhulp); over welk model en welke uitvoering het echt gaat. De titel en
`verzameld.modellen_kandidaat` zijn vermoedens: een titel noemt soms de concurrent in plaats van de auto.

**Geen review of onbruikbaar:** schrijf alleen `oordeel.json` met `is_review: false` en de reden.

**Wel bruikbaar:** schrijf drie bestanden.

1. `oordeel.json`: `{"is_review": true, "reden": "...", "taal_transcript": "...", "bronpagina_bestand":
   "JJJJ-MM-DD-<slug>.md", "modellen": [], "merken": [], "kanaal": "<slug>", "vergelijking": true|false,
   "waarschuwingen": []}`
2. `bron.md`: de volledige bronpagina volgens het contract en de precedenten: frontmatter met `type`,
   `kind`, `title`, `author`, `url`, `date_published`, `date_ingested`, `length`, `raw`, `tags`, `merken`,
   `modellen`, `feitsoorten`, `concurrenten` (`model`, `tegen`, `tijd`, `grond`), `weergaven`,
   `vergelijking` (als het een vergelijking is) en `relationships` (`published-by` naar het kanaal).
   Body: beschrijving van het kanaal als blockquote, Samenvatting (met het belang als het kanaal zelf
   leaset of verkoopt), secties per feitsoort met tijdstempel-links
   `[m:ss](https://www.youtube.com/watch?v=<id>&t=<s>s)`, Concurrenten, Wat er gelezen is, Weergaven
   (aantal en per dag sinds publicatie), Gekoppelde pagina's.
3. `voorstel.json`:
   `{"nieuwe_entiteiten": [{"slug","kind","naam","merk","plinkie_pad","aliases","tekst"}],
   "model_feiten": {"<model>": {"uitvoeringen": [], "fabrieksopgaven": [], "metingen": [], "valkuilen": [],
   "oordelen": [], "concurrenten": [{"tegen","tijd","grond"}]}}, "merk_feiten": {"<merk>": []},
   "concepten": [{"slug","bestaat","toevoeging"}], "relaties_met_bestaande_bronnen": [{"type","target","via"}]}`.
   Elk feit noemt de uitvoering (of "uitvoering niet genoemd") en eindigt met de tijd.

## Regels
- Slugs: model = `<merk>-<model>` uit het Plinkie-pad; merk = het merkdeel; een uitvoering (GSE, HF, GTX)
  is geen eigen model. Een model dat Plinkie niet heeft, krijgt dezelfde vorm met `plinkie_pad: ""`.
- Getallen uit spraakherkenning zijn vermoedens: wat niet klopt, schrijf je als *"(transcript: '…')"*,
  niet als feit. Prijzen alleen als ze leesbaar zijn, met de datum van de bron.
- `meting` alleen voor wat de tester zelf mat, met omstandigheden. Fabrikantcijfers zijn `fabrieksopgave`.
- Concurrenten: wat de tester als concurrent of alternatief noemt, plus elk paar van verschillende
  merken in een vergelijking. Twijfel over welk model het is: niet opnemen, wel in de tekst noemen.
- Nederlands, korte zinnen, eigen woorden. Geen git.

Eindig met hooguit tien regels: is het bruikbaar, welke modellen, welke concurrenten, en wat de
samenvoegstap moet weten (twijfels, onleesbare getallen, nieuwe entiteiten).
