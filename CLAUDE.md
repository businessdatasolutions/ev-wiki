# CLAUDE.md

Dit bestand is de werkwijze voor Claude Code in deze repository.

## Wat deze repository is

Dit is **geen softwareproject**. Het is een **LLM-wiki** over elektrische auto's, naar het patroon
in `llm-wiki.md` (Andrej Karpathy). Claude bouwt en onderhoudt stap voor stap een blijvende,
onderling gelinkte kennisbank in markdown, uit bronnen die de gebruiker kiest. Kennis wordt één
keer verwerkt en bijgehouden, niet per vraag opnieuw afgeleid.

De bronnen zijn vooral **reviews en tests van elektrische auto's** (YouTube, tijdschriften,
testrapporten). De wiki is werkmateriaal voor **Plinkie**, de vergelijker van private lease voor
elektrische auto's. Plinkie gebruikt hem om modelpagina's te verrijken met wat testers meten en
wat de configurator niet zegt. De wiki is **geen** bron van waarheid voor Plinkie: een feit uit
deze wiki gaat bij Plinkie eerst door een controle bij de fabrikant of aanbieder. De afweging staat
in Plinkie's `ideeen/plinkie-reviews.html`.

**Taal: Nederlands.** Wiki-pagina's, logregels en deze werkwijze zijn Nederlands. Code en
scripts die uit de ai-wiki komen, houden hun Engelse commentaar.

**Herkomst.** Opgezet op 06-10-2026 als kopie van het systeem van
[`businessdatasolutions/ai-wiki`](https://github.com/businessdatasolutions/ai-wiki) (Quartz v4,
levenscyclus, graaf, retentie, kwaliteit, zoeken, hooks), zonder de inhoud en zonder de
git-geschiedenis. Dit is een eigen wiki en geen fork die upstream volgt. De
Warner & Wäger-tagging van de ai-wiki is vervangen door de [§EV-lens](#ev-lens).
`llm-wiki-v2.md` is meegenomen als achtergrond.

## Huidige stand

- `raw/`: bronmateriaal per soort (`videos/`, `articles/`, `reports/`, `images/`). Onveranderlijk.
- `wiki/`: `sources/`, `entities/`, `concepts/`, `threads/`, `syntheses/`, `assets/`, plus
  `index.md` en `log.md`. Kruisverwijzingen alleen met `[[wikilinks]]`.
- Frontmatter: `type: source | entity | concept | thread | synthesis`; `kind:` op entiteiten en bronnen.
- Logregels: `## [JJJJ-MM-DD] <op> | <titel>`, met `<op>` ∈ `ingest | acquire | query | lint |
  synthesize | refactor | bulk-refactor`. Nieuwste bovenaan.
- Publicatie met Quartz naar GitHub Pages: `businessdatasolutions.github.io/ev-wiki`.

## De lagen

1. **Ruwe bronnen** (`raw/`): gekozen door de gebruiker of opgehaald door de
   [verzamelaar](#verzamelaar), onveranderlijk. Claude leest, wijzigt nooit. Het register van wat
   de verzamelaar zag en waarom hij iets oversloeg, staat in `onderzoek/`.
2. **De wiki** (`wiki/`): de onderzoekslaag, door Claude geschreven en beheerd. Samenvattingen,
   entiteiten, concepten, syntheses, een index en een log.
3. **Artikelen** (nog niet gebouwd): de publicatielaag, een kritisch artikel per model, geschreven
   uit de wiki en pas live na de poort in Plinkie's `ideeen/plinkie-reviews.html#poort`. Artikelen
   komen nooit in `raw/` of tussen de onderzoekspagina's.
4. **Het schema**: dit bestand. Het contract dat van Claude een gedisciplineerde beheerder maakt.

## De vier operaties

**Ingest** (= Acquire + Process), **Query**, **Lint** en **Synthesize**.

### Acquire

Een nieuw ruw bestand landt in `raw/`. Acquire raakt **alleen** `raw/`.

1. **Kies de map op soort, niet op onderwerp**: `videos/`, `articles/`, `reports/`, `images/`.
   Maak een nieuwe soortmap aan als er echt een nieuwe soort bijkomt.
2. **Zet om vóór het landen.** PDF → markdown (`marker`, `markitdown`, `pdftotext`), de PDF
   ernaast en gitignored. Webpagina → markdown.
3. **YouTube**: gebruik de skill [`youtube-transcript-skill`](.claude/skills/youtube-transcript-skill/SKILL.md),
   **altijd met `--sub-lang nl` bij een Nederlandse video**:

   ```bash
   cd .claude/skills/youtube-transcript-skill
   uv run --no-project --with-requirements requirements.txt \
     python fetch_transcript.py "<url>" --sub-lang nl --timeout 60000 -o ../../../raw/videos/<slug>.md
   ```

   Met `--sub-lang` haalt de skill metadata en ondertitels in **één yt-dlp-aanroep, zonder
   browser**: twee verzoeken per video in plaats van vier tot zes. Een automatisch spoor telt alleen
   in de taal van de video zelf, zodat er nooit een machinevertaling binnenkomt. Lukt het niet,
   dan valt de skill terug op het transcriptpaneel in de browser; dan ontbreekt `transcript_track`
   en kan de tekst in een andere taal zijn. Zonder `--sub-lang` kiest het paneel zelf een spoor,
   en dat was op 06-10-2026 bij een Autovisie-review het Engelse. De skill zet `view_count_date:` naast `view_count:`: het aantal
   weergaven is een momentopname en zonder dag niet te vergelijken.
4. **Opnieuw ophalen mag.** Een betere versie van dezelfde bron vervangt het ruwe bestand; de
   wiki-pagina verandert pas bij een nieuwe Process. **Uitzondering:** draai `fetch_transcript.py -o`
   nooit opnieuw op een bestaand pad met handgeschreven `notes:`. Voor een nieuwe weergavenmeting
   lees je alleen het getal (`--json`) en zet je het als meting op de bronpagina.
5. **Logregel**: alleen als Acquire zonder Process draait: `acquire | <slug of batch>`.
   Draaien ze samen, dan is het één `ingest | ...`.

### Process

0. **Controleer identiteit en volledigheid** ([§Bronnen controleren](#bronnen-controleren-vóór-ingest)).
1. Lees de bron helemaal.
2. Bespreek de kern met de gebruiker vóór het schrijven (standaard één bron tegelijk, tenzij de
   gebruiker om een batch vraagt).
3. Schrijf de bronpagina in `wiki/sources/<JJJJ-MM-DD>-<slug>.md`.
4. **Vul de EV-lens in**: `merken:`, `modellen:`, `feitsoorten:`, `concurrenten:` en (bij video)
   `weergaven:` ([§EV-lens](#ev-lens), [§Concurrentie](#concurrentie)).
5. **Zoek buurbronnen** met de skill [`neighbour-source-scan`](.claude/skills/neighbour-source-scan/SKILL.md):
   bronnen over hetzelfde model, over hetzelfde merk, en bronnen met dezelfde conceptpagina's.
   Leg per buur een getypeerde relatie vast of laat het bewust weg. Bij drie of meer kandidaten:
   noem de lijst.
6. **Werk elke geraakte entiteit en elk geraakt concept bij.** Eén ingest raakt al snel 10–15
   bestanden. Zet op elke geraakte pagina `last_confirmed` en `accessed_at` op vandaag en reken
   `source_count` en `confidence` opnieuw uit ([§Levenscyclus](#levenscyclus)). Op een modelpagina:
   zet elk nieuw feit in de juiste sectie, met uitvoering, bron en tijdstempel, en werk de
   `competes-with`-randen bij uit `concurrenten:`. Op een merkpagina:
   wat over het merk gaat (dealers, garantie, importeur, concern).
7. **Werk `index.md` bij.** Elke geschreven of geraakte pagina heeft een eigen regel. Bronnen per
   ingestbatch, nieuwste batch bovenaan, binnen de batch nieuwste publicatiedatum eerst. Entiteiten,
   concepten, syntheses en threads alfabetisch. Controleer met `node scripts/lint-index-completeness.mjs`.
8. **Zet een logregel bovenaan `log.md`**, direct onder de `---`.
9. **Tegenspraak** met een oudere bewering komt in `## Debatten en vervanging` van de pagina. Vervangt
   een bron een oudere volledig, volg dan het [vervangingsprotocol](#vervangingsprotocol).

### Query

1. Lees eerst `index.md`; bij meer dan vijf kandidaatpagina's eerst zoeken ([§Zoeken](#zoeken)).
2. Antwoord **met bronverwijzingen** naar wiki-pagina's en waar nodig naar ruwe bronnen.
3. De vorm volgt de vraag: tabel, vergelijking, grafiek, pagina.
4. **Een goed antwoord gaat terug de wiki in** als nieuwe pagina, met index- en logregel.

### Lint

Periodieke gezondheidscontrole: tegenspraak tussen pagina's, verouderde beweringen, wezen
(pagina's zonder inkomende link), concepten zonder eigen pagina, ontbrekende kruisverwijzingen,
en vragen die een nieuwe bron verdienen. Rapporteer; de gebruiker beslist.

| Script | Controleert | Exit |
| --- | --- | --- |
| `scripts/lint-page.mjs` | Levenscycluscontract, relatiewoordenlijst, lichaamswikilinkregel, EV-lens, datumvoorvoegsel van bronnen. Draait als hook bij elke bewerking | altijd 0 |
| `scripts/lint-confidence.mjs` | `confidence` binnen bereik en verdedigbaar | ≠0 bij bevindingen |
| `scripts/lint-dangling-authors.mjs` | Auteurs op ≥2 bronnen zonder entiteitspagina | ≠0 bij bevindingen |
| `scripts/lint-index-completeness.mjs` | Pagina's zonder regel in `index.md` | ≠0 bij bevindingen |
| `scripts/lint-collapse.mjs` | Pagina's die bij herschrijven detail verliezen | ≠0 bij bevindingen |

`lint-page.mjs` leest een JSON-payload op **stdin** en schrijft naar **stderr**. Een pad als
argument geeft stil exit 0, en dat lijkt op een geslaagde controle. Voor de hele wiki:

```bash
find wiki -name '*.md' -not -name 'index.md' -not -name 'log.md' | sort | while read f; do
  printf '{"tool_input":{"file_path":"%s"}}' "$f" | node scripts/lint-page.mjs
done
```

Wezen opsporen heeft geen script; dat is een handmatige ronde.

## Verzamelaar

`onderzoek/verzamelaar.py` haalt **zelfstandig** reviews op. Het is Acquire, geautomatiseerd: hij
schrijft in `raw/videos/` en `onderzoek/`, plus één `acquire`-regel in `wiki/log.md`, en **nooit**
een wiki-pagina. Process blijft een sessie met een mens erbij; de SessionStart-hook toont hoeveel
ruwe video's erop wachten.

**Wanneer.** Elke nacht om 04:15 via launchd (`onderzoek/installeer-planning.sh` zet hem aan,
`onderzoek/nl.businessdatasolutions.ev-wiki.verzamelaar.plist` is de taak). Met de hand:
`onderzoek/verzamel.sh [--droog] [--verken] [--max N]`. Logs in `onderzoek/logs/` (niet in git).

**Gewone run.**
1. De modellen komen uit de sitemap van plinkie.nl: alleen auto's die Plinkie aanbiedt.
2. Per kanaal in `onderzoek/kanalen.yaml` (`vast:`) de nieuwste uploads, met titels in de taal van
   het kanaal.
3. Een titel wordt aan een model gekoppeld als **merk én model** erin staan. Een model van één
   teken (Renault 4) telt alleen direct na het merk; een model binnen een ander model ("e-tron" in
   "Q4 e-tron") valt weg. Getest in `onderzoek/test_verzamelaar.py`.
4. Overgeslagen: geen model, korter dan 4 minuten, of een titel onder `uitsluiten:` van het kanaal
   (bij ANWB de Wegenwacht-afleveringen).
5. Opgehaald met de transcript-skill en `--sub-lang` in de taal van het kanaal, hooguit 8 per run,
   met 15 seconden tussen twee video's. **YouTube beperkt per verbinding** (HTTP 429): de skill wacht
   30 en 90 seconden en probeert opnieuw, en strandt een video toch op een 429, dan haalt de run
   niets meer op. Parallel ophalen helpt hier niet: alle processen delen één verbinding.
   De ruwe kop krijgt een blok `verzameld:` (door, datum, kanaal, `modellen_kandidaat`).

**Verkenning** (eens per week, of `--verken`). Voor 15 modellen per keer, op volgorde rond door de
lijst, zoekt hij op YouTube ("<model> review", "<model> test", Nederlands en Engels). Kanalen
buiten de lijst worden **niet opgehaald**: ze komen als voorstel in `onderzoek/kanaalvoorstellen.md`,
per kanaal met modellen, aantal video's en voorbeelden. **Alleen de gebruiker** zet een kanaal in
`vast:` of `genegeerd:`.

**Register.** `onderzoek/register.jsonl` heeft één regel per video die de verzamelaar zag, met
status (`opgehaald`, `overgeslagen` met reden, `mislukt`, `voorstel`). Een video in het register of
in `raw/` wordt niet opnieuw bekeken. Wil je een overgeslagen video toch, haal hem dan met de hand op.

**Bij Process van een verzamelde video.** `modellen_kandidaat` is een vermoeden uit de titel, geen
feit: controleer in het transcript over welk model en welke uitvoering de video echt gaat, en of het
een review is. Is het geen review, schrijf dan geen bronpagina maar zet in het register een regel
met status `afgewezen` en de reden.

## Bronnen controleren vóór ingest

Bestandsnamen liegen, fragmenten doen zich voor als hele bronnen, en spraakherkenning verminkt
getallen. **Meld een afwijking vóór je wiki-pagina's schrijft.**

### Video's: het frontmattercontract

De skill schrijft deze kop (verkort; de skill levert ook `thumbnails`, `keywords`, `chapters` en meer):

```yaml
---
title: <titel>
video_id: <youtube-id>
url: <url>
channel: <kanaal>
publish_date: '<ISO-8601 met tijdzone>'
duration: '<MM:SS>'
length_seconds: <geheel getal>
view_count: <geheel getal>
view_count_date: '<JJJJ-MM-DD>'      # de dag waarop het aantal is gelezen
caption_tracks: [...]
transcript_track: {language_code: nl, kind: asr | manual, via: yt-dlp}
description: |
  <beschrijving van het kanaal>
---
```

**Verplicht voor pre-flight:** `title`, `url`, `channel`, `publish_date`. Ontbreekt er één, stop en vraag.
**Controleer de taal:** `transcript_track.language_code` hoort de taal van de video te zijn.

#### Veldmapping video → bronpagina

| Ruw | Bronpagina | Omzetting |
| --- | --- | --- |
| `title:` | `title:` | tussen aanhalingstekens bij een `:` |
| `channel:` | `author:` | lijst met één element |
| `url:` | `url:` | letterlijk. Zet ook **▶ Bekijk op YouTube** op de pagina via `inject-video-link.ts` |
| `publish_date:` | `date_published:` + voorvoegsel bestandsnaam | alleen de datum |
| `duration:` + aantal regels | `length:` | `"~MM:SS minuten (transcript ~N regels)"` |
| `view_count:` + `view_count_date:` | `weergaven:` | eerste meting `{datum, aantal}` ([§EV-lens](#ev-lens)) |
| `transcript_track.kind` | kwaliteitsregel in de tekst | `asr` → "automatisch transcript"; `manual` → "transcript van het kanaal" |
| `description:` | blockquote bovenaan de tekst | verplicht: de eigen omschrijving van het kanaal vóór die van de wiki |
| `chapters:` | optioneel als tussenkoppen | |

Vaste velden: `kind: video`, `raw: "../../raw/videos/<slug>.md"`, `url:` verplicht.

### Getallen uit spraakherkenning

**Een getal uit een automatisch transcript is een vermoeden, geen feit.** In één ANWB-video
kwamen prijzen via het transcriptpaneel terug als "€0.00", "€9.99" en "€2 3.4", en in een
Autovisie-video werd de SEPP-subsidie "€300 aan Seb subsidie". Regels:

1. Schrijf een getal pas op als het in de zin klopt (eenheid, orde van grootte, vergelijking met
   een ander getal in dezelfde video). Twijfel? Zet het erbij als *"(transcript: '…')"* en schrijf
   het niet als feit.
2. Een getal dat de fabrikant ook publiceert (accu, WLTP, vermogen) heet `fabrieksopgave`, ook als
   de tester het noemt. Het is pas gecontroleerd als het tegen de fabrikant is gelegd; zeg dat.
3. Een **eigen meting** van de tester (verbruik, bereik op een rit, laadtijd) is het waardevolste
   en het kwetsbaarste getal: noem altijd de omstandigheden (temperatuur, route, uitvoering) en de
   tijdstempel.

### Controle 1: Omvang
Is dit de hele bron? Bij een video: komt het laatste tijdstempel in de buurt van `duration:`?

### Controle 2: Identiteit
Levert de inhoud wat de titel belooft? Gaat de video over de auto die de titel noemt, en welke
uitvoering?

### Controle 3: Eerlijke afbakening
`length:` zegt wat er gelezen is. Een video uit 2024 noemt subsidies, prijzen en "launch editions"
die nu anders kunnen zijn: zet bovenaan de bronpagina wanneer de video is gemaakt en wat
daardoor verouderd kan zijn.

## Werkprincipes

- **De wiki is Claude's codebase.** Vijftien bestanden in één ingest is normaal.
- **Kruisverwijzingen zijn het product.** Een pagina zonder links is niet af.
- **Boekhouden is het werk**: index, log, kruisverwijzingen, consistentie, zonder dat het twee
  keer gevraagd hoeft te worden.
- **Bronnen zijn onveranderlijk.** Bestanden in `raw/` alleen lezen.
- **Eerst controleren, dan vertrouwen.**
- **De uitvoering hoort bij het feit.** "De Kia EV2 haalt 453 km" is half waar: dat is de 61 kWh.
  Elk feit op een modelpagina noemt de uitvoering, of zegt dat de bron die niet noemt.
- **Wie zegt het?** Een review van een partij die de auto zelf verkoopt of leaset (ANWB heeft
  ANWB Private Lease) is een bron met een belang. Dat staat op de kanaalpagina en telt mee in
  `confidence`.
- **Schema meegroeien.** Wat goed of slecht werkt, komt in dit bestand terecht.

## EV-lens

De ai-wiki taggde bronnen met Warner & Wäger. Deze wiki heeft een eigen lens, op wat een bron over
een auto zegt.

### Frontmattercontract (bronpagina's)

```yaml
merken: [dongfeng]                      # slugs van merkpagina's in wiki/entities/
modellen: [dongfeng-box]                # slugs van modelpagina's in wiki/entities/
feitsoorten: [meting, valkuil, oordeel] # uit de gesloten lijst hieronder
weergaven:                              # alleen bij video; één regel per meting
  - datum: 2026-10-06
    aantal: 31788
```

- **`merken:`** de merken waar de bron **over gaat**. Altijd het merk van elk model in
  `modellen:`, plus een merk waarover de bron iets zegt zonder een model te bespreken (dealers,
  garantie, importeur). Een merk dat alleen als concurrent valt, hoort er niet in.
- **`modellen:`** de modellen waar de bron **over gaat**, niet elke auto die als concurrent valt.
- Elk slug uit `merken:` en `modellen:` staat ook als `[[wikilink]]` in de tekst (lint
  controleert dat), en lint waarschuwt als een model in `modellen:` staat zonder zijn merk in `merken:`.
- **`feitsoorten:`** gesloten lijst. De definities staan op één plek:
  [[concepts/feitsoorten|feitsoorten]].

  | Soort | Wat het is |
  | --- | --- |
  | `fabrieksopgave` | herhaald wat de fabrikant publiceert: accu, WLTP, vermogen, prijs |
  | `meting` | wat de tester zelf mat: verbruik, bereik op een rit, laadtijd, kofferbak gemeten |
  | `valkuil` | wat de keuze verandert en de configurator niet zegt, per uitvoering |
  | `oordeel` | mening van de tester: rijgedrag, geluid, stoelen, bediening |
  | `merk-en-service` | dealernetwerk, garantie, restwaarde, importeur, crashtest |

  **Lichaamstweeling:** elke feitsoort komt als woord terug in de tekst, liefst als tussenkop.
- **`weergaven:`** het aantal weergaven met de dag waarop het gelezen is. **Een nieuwe meting
  komt erbij; een oude wordt nooit overschreven.** De groei tussen twee metingen is het signaal
  voor belangstelling, niet één stand. Vergelijk alleen binnen één kanaal, en reken per dag sinds
  publicatie (`aantal / dagen tussen date_published en datum`). Een vergelijkingstest telt voor
  elk model in `modellen:`. Dit is een signaal voor Plinkie's volgorde van werk, geen
  populariteitslabel.

### Modelpagina's (`kind: model`)

```yaml
type: entity
kind: model
merk: kia                       # slug van de merkpagina
plinkie_pad: /deals/kia/ev2     # alleen als nagegaan dat Plinkie dit pad heeft; anders leeg
aliases: [EV2, Kia EV2]
relationships:
  - type: part-of
    target: kia
```

`plinkie_pad` is de koppelsleutel naar Plinkie (`/deals/<merk>/<model>`). Nagaan doe je in de
openbare sitemap, `https://plinkie.nl/sitemap.xml`; dat is ook de modellenlijst van de verzamelaar.
Plinkie kent sommige modellen onder twee paden (`renault/4` en `renault/4-e-tech`); `plinkie_pad`
noemt het kortste. Plinkie maakt het pad uit
de voertuigsleutel: kleine letters, zonder accenten, woorden met `-` (`Citroën ë-C3` → `citroen/e-c3`,
`ID.3` → `id3`), met de aliaslijst in Plinkie's `aliassen.json`. **Vul het alleen in als het in
Plinkie is nagegaan**: een verzonnen pad is een stille gebroken koppeling. Leeg betekent "nog niet
gekoppeld", niet "Plinkie heeft hem niet".

Vaste secties, in deze volgorde, elk feit met uitvoering en een link naar de bron met tijdstempel:

1. `## Uitvoeringen`: accu's, vermogens, pakketten, zoals de bronnen ze noemen.
2. `## Fabrieksopgaven`
3. `## Metingen`: tabel met tester, datum, uitvoering, omstandigheden, waarde, fabrieksopgave ernaast.
4. `## Valkuilen`
5. `## Oordelen`
6. `## Concurrenten`: elke tegenhanger met wie hem noemde, wanneer en waarom (prijs, klasse, maat).
7. `## Weergaven`: per bron de laatste meting en het aantal per dag.
8. `## Debatten en vervanging`

Een model dat alleen als concurrent genoemd wordt, krijgt ook een modelpagina, maar kort:
frontmatter, één alinea en `## Concurrenten`. Zo heeft elke rand een doel, en groeit de pagina
vanzelf als er later een review van dat model bijkomt.

Wat over het merk gaat en niet over dit model, staat op de merkpagina.

### Concurrentie

Testers zeggen vaak tussendoor: *"deze concurreert met X van merk A en Y van merk B"*. Dat is voor
Plinkie goud: het is de basis voor een knop **"Vergelijkbare auto's"** bij een aanbieding, met
daarachter de aanbiedingen van de alternatieven. Daarom wordt het op twee plekken vastgelegd.

**1. Op de bronpagina, als bewering:**

```yaml
concurrenten:
  - model: kia-ev2
    tegen: [fiat-grande-panda, citroen-e-c3, byd-dolphin-surf]
    tijd: "2:07"
    grond: "B-segment, goedkoper dan de EV2"
  - model: kia-ev2
    tegen: [renault-4, jeep-avenger]
    tijd: "2:21"
    grond: "B-segment, duurder"
```

- `model` en elke slug in `tegen` hebben een modelpagina (lint controleert dat).
- `tijd` is het tijdstempel in de video, verplicht bij `kind: video`.
- `grond` zegt waarom de tester ze naast elkaar zet: prijs, klasse, maat, merkimago, een
  rechtstreekse vergelijkingstest. Een vergelijkingstest van twee modellen is de sterkste grond.
- **Een vergelijking is automatisch concurrentie** (besluit eigenaar, 06-10-2026). Zet een video
  of artikel twee of meer modellen van **verschillende merken** naast elkaar (een
  vergelijkingstest, "X tegen Y", een occasion battle), dan zijn ze elkaars concurrent, ook als
  het woord niet valt: dat het medium ze vergelijkt, is de grond. Zet dan `vergelijking: true` op
  de bronpagina; lint eist dat elk paar van verschillende merken in `concurrenten:` staat.
  Modellen van hetzelfde merk in één vergelijking (Kia EV3 tegen EV2) vallen er niet automatisch
  onder: dat is een keuze binnen één merk, geen alternatief bij een andere aanbieder.
- Neem verder alleen op wat de tester **als concurrent of alternatief** noemt. Een model dat ter
  vergelijking van één maat valt ("de Epiq heeft 490 liter"), telt mee als het in dezelfde
  passage als alternatief wordt gezet; een losse vermelding van een ander merk niet.

**2. Op de modelpagina, als rand:**

```yaml
relationships:
  - type: competes-with
    target: fiat-grande-panda
    via: "ANWB 01-04-2026 (2:07): B-segment, goedkoper"
```

- Eén rand per paar per modelpagina, met in `via` alle bronnen die het paar noemen. Komt er een
  bron bij die hetzelfde paar noemt, dan breidt `via` uit en gaat de `confidence` van de rand
  omhoog volgens de gewone regels. **Het aantal bronnen dat een paar noemt is de sterkte**.
- De rand staat op de pagina van het model **waarover de bron gaat**. De omgekeerde richting rekent
  `scripts/graph-export.mjs` uit; schrijf hem niet dubbel.
- Zet het paar ook als `[[wikilink]]` in `## Concurrenten` (de lichaamswikilinkregel).

Plinkie leest dit uit `wiki/.graph.json` (randen van klasse `market`) of uit de frontmatter.
Concurrentie volgens een tester is een **suggestie**, geen gelijkwaardigheid: twee auto's in
hetzelfde segment kunnen een andere accu, kofferbak of trekhaak hebben. Wat Plinkie ermee doet,
beslist Plinkie.

### Merkpagina's (`kind: merk`)

Fabrikant, concern, importeur in Nederland, dealer- en servicenetwerk, garantie, en de modellen
in de wiki. Een merk is `part-of` zijn concern als dat een eigen pagina heeft.

### Entiteitssoorten

`kind:` op entiteiten: `model | merk | aanbieder | kanaal | organisatie | persoon | plek | evenement`.

- **`kanaal`**: wie de review maakte (ANWB, Autovisie). Een kanaal krijgt meteen bij de eerste bron
  een pagina, want het veld `ook_aanbieder:` moet ergens staan:
  `ook_aanbieder: anwb-private-lease` als het kanaal ook leaset of verkoopt.
- **`aanbieder`**: een leasemaatschappij zoals Plinkie ze toont.
- **Personen** (presentatoren) volgen de regel van twee bronnen ([§Auteurs promoveren](#auteurs-promoveren)).

### Het filtermodel van Plinkie

De wiki gebruikt dezelfde woorden als Plinkie. De filters en sorteringen van Plinkie staan als
bron in `wiki/sources/2026-10-06-plinkie-filtermodel.md`, met elk filter als concept
(carrosserie, prijsklasse, EerlijkePrijs, rijbereik WLTP, snelladen 10–80%, kilometerbundel,
looptijd) en elke aanbieder en elk merk als entiteit. Verandert het filtermodel van Plinkie, dan
komt er een nieuwe momentopname als bron en wordt de oude `status: stale`.

## Levenscyclus

### Frontmattercontract (concepten en entiteiten)

- `confidence: 0.0–1.0`: hoe sterk de bronnen in de wiki de pagina dragen.
- `last_confirmed: JJJJ-MM-DD`: laatste ingest die de pagina versterkte.
- `source_count: N`: aantal bronpagina's dat de pagina draagt.
- `accessed_at: JJJJ-MM-DD`: laatste keer dat de pagina in context werd gelezen.

Concepten en syntheses dragen daarnaast `quality_score` en `quality_notes`, geschreven door
`scripts/quality-score.mjs`. Bronnen dragen **geen** `confidence`: bronnen zijn bewijs.

### Regels voor `confidence`

- Eén bron: `0.7`. Elke volgende bron: `+0.05`, tot `0.95`.
- Een tegensprekende bron in `## Debatten en vervanging`: `−0.1`.
- Eigen meting van een onafhankelijke tester met omstandigheden erbij: `+0.05` (één keer).
- Een bron met een belang (de tester verkoopt of leaset het model), een eerste kennismaking zonder
  eigen meting, of alleen fabrieksopgaven: niet boven `0.75` zolang er geen onafhankelijke tweede bron is.
- **`0.95` is een harde grens.** Wil een pagina hoger, zeg dan in de tekst wat de pagina is voor de wiki.
- Nooit `0.0` als standaard.

### Vervangingsprotocol

Als nieuwe data een oudere bewering volledig vervangt:

1. De oude pagina houdt haar inhoud. Nooit leegmaken of verwijderen.
2. De oude pagina krijgt `status: stale` en `superseded_by: [[nieuwe-pagina]]`.
3. De nieuwe pagina krijgt `supersedes: [[oude-pagina]]`.
4. `inject-stale-banner.ts` zet op de site een waarschuwing bovenaan de oude pagina.
5. Logregel met `op: refactor`.

Voegt nieuwe data alleen nuance of tegenspraak toe, dan is de oude pagina niet verouderd: zet een
regel in `## Debatten en vervanging`.

### Debatten en vervanging

Concept- en modelpagina's met meer dan één bron hebben onderaan `## Debatten en vervanging`:
open tegenspraak (wie zegt X, wie niet-X, waar het op draait), vervangingen, en open vragen.
Bij auto's draait tegenspraak vaak om de uitvoering of de temperatuur: zeg dat.

### Auteurs promoveren

Iedereen in `author:` staat in de bron. Een **persoon** krijgt pas een eigen pagina bij de tweede
bron; tot dan staat hij onder "**Los** (één bron)" op de bronpagina. Kanalen zijn de uitzondering
(zie §Entiteitssoorten). Controle: `node scripts/lint-dangling-authors.mjs`.

## Retentie

Kennis veroudert. Voor concepten, entiteiten en syntheses rekent lint een *effectieve* zekerheid:

```
effectieve_confidence = confidence × exp(-dagen_sinds_accessed_at / tau)
```

`tau` is 90 dagen voor concepten en syntheses, 365 voor entiteiten, oneindig voor bronnen. Het is
een signaal, nooit een automatische bewerking: verval verwijdert niets, zet niets op `stale` en
overschrijft `confidence` niet. `accessed_at` gaat omhoog bij een ingest, bij een query (`/wq`
doet dat zelf) of met `node scripts/bump-accessed.mjs <slugs>`.

Bij auto's veroudert een **prijs** veel sneller dan de rest: een prijs op een wiki-pagina noemt
altijd de bron en de datum, en is nooit een actuele prijs. Actuele prijzen staan bij Plinkie.

## Kwaliteit

`node scripts/quality-score.mjs` scoort concepten en syntheses op structuur (0,40),
bronverwijzingen per 1000 woorden (0,30) en interne samenhang (0,30), en schrijft
`quality_score` en `quality_notes` terug. Onder 0,65 eerst repareren, vóór er nieuwe bronnen
bijkomen. `--dry-run` schrijft niets, `--page <slug>` scoort één pagina. Dit zijn de enige
frontmattervelden die een script mag schrijven.

## Zoeken

Lokaal zoeken met [qmd](https://github.com/tobi/qmd) (`@tobilu/qmd`): BM25, vectoren en
herrangschikking, op het eigen apparaat. De collectie heet **`ev-wiki`**; de zoekscripts
filteren erop (`-c ev-wiki`), zodat er nooit treffers uit de ai-wiki tussen komen.

Eenmalig registreren:

```sh
npx @tobilu/qmd collection add ./wiki --name ev-wiki --mask '**/*.md'
npx @tobilu/qmd context add qmd://ev-wiki "Kennisbank over elektrische auto's: reviews, metingen, valkuilen per uitvoering, voor Plinkie"
```

Na elke ingest: **eerst `update`, dan `embed`**, anders komen nieuwe pagina's er niet in:

```sh
npx @tobilu/qmd update && npx @tobilu/qmd embed -c ev-wiki
```

- `/wq <vraag>`: snel zoeken via `scripts/wiki-query.mjs`, met `accessed_at`-bump.
- `/wqa <vraag>`: antwoord met volledig spoor via de skill `traceable-wiki-answer` en
  `scripts/wiki-retrieve.mjs` (qmd en graaf samen).
- Een bekende pagina: gewoon `index.md`.

## Graaf

### Relaties in frontmatter

```yaml
relationships:
  - type: contradicts
    target: 2024-11-15-chinese-evs-onder-de-25-mille-kleine-autos-grote-verleiding
    via: "praktijkbereik bij 7 °C"
```

`target` is een slug, geen wikilink. `via` zegt waar het op draait. `confidence` is optioneel.

| Type | Klasse | Gebruik |
| --- | --- | --- |
| `competes-with` | markt | A en B worden door een tester als alternatief naast elkaar gezet ([§Concurrentie](#concurrentie)) |
| `supports` | bewijs | A versterkt B |
| `contradicts` | bewijs | A botst met B; altijd met `via` |
| `supersedes` | bewijs | A vervangt B; met het vervangingsprotocol |
| `caused` | oorzaak | A leidde tot B |
| `fixed` | oorzaak | A lost B op (bijv. een software-update) |
| `part-of` | structuur | A hoort bij B (model `part-of` merk, merk `part-of` concern) |
| `instance-of` | structuur | A is een geval van B (Box `instance-of` eenfase-laden) |
| `depends-on` | structuur | A werkt niet zonder B |
| `uses` | structuur | A gebruikt B (model `uses` LFP-accu) |
| `authored-by` | herkomst | A komt van B |
| `published-by` | herkomst | A verscheen via B (bron `published-by` kanaal) |
| `employs` | herkomst | A heeft B in dienst |

Omgekeerde richtingen worden niet opgeslagen: `scripts/graph-export.mjs` rekent ze uit naar
`wiki/.graph.json` (gitignored).

### Lichaamswikilinkregel (draagt gewicht)

**Elke relatie in frontmatter staat ook als `[[wikilink]]` in de tekst, met minstens één zin
context.** Frontmatter is de getypeerde laag, de tekst de navigeerbare. Lint controleert beide kanten.

### Wikilinks en Quartz

**Nooit opmaak binnen de alias van een wikilink**: `*[[doel|alias]]*`, niet `[[doel|*alias*]]`.
Obsidian toont het goed, Quartz breekt het pas na de publicatie. Een alt-tekst van een afbeelding
eindigt nooit op een getal: Quartz leest dat als breedte.

## Synthese

Een `wiki/threads/`-pagina is voorlopig: een vraag, kandidaatbronnen en een plan. Als er genoeg
bronnen zijn, wordt de thread een `wiki/syntheses/`-pagina met `derived_from`, `opened`, `closed`
en de secties **Vraag**, **Bevindingen**, **Geraadpleegde bronnen**, **Lessen**, **Open vragen**.
De thread krijgt `status: closed`, `index.md` en `log.md` (`synthesize`) worden bijgewerkt.

Typische vragen hier: *"Hoeveel minder dan WLTP rijden testers met kleine EV's in de winter?"*,
*"Welke modellen onder € 30.000 laden thuis op één fase?"*

## Video-stills (optioneel)

`extract_stills.py` uit de skill haalt beelden met informatie uit een video (tabellen,
specificatieschermen, een getoonde meting). Bij autoreviews vooral nuttig voor **getallen in
beeld** die de spraak verminkt. Werkwijze, kosten en de publicatieregel (alleen gecontroleerde,
geselecteerde stills als webp in `wiki/assets/<pagina-slug>/`, met kanaal en tijdstempel) staan in
de [skill](.claude/skills/youtube-transcript-skill/SKILL.md). Elke still is gelezen door een
model: controleer hem tegen de pixels voor je iets overneemt.

## Hooks

Ingesteld in [`.claude/settings.json`](.claude/settings.json).

**Regel die niet onderhandelbaar is:** een hook mag naar `wiki/log.md`, naar lintuitvoer en naar
gitignored afgeleiden (`wiki/.graph.json`) schrijven, **nooit** naar een inhoudspagina of `index.md`.

| Gebeurtenis | Script | Doel |
| --- | --- | --- |
| `SessionStart` | `scripts/session-start.mjs` | Korte stand van de wiki als context |
| `PostToolUse` (Edit, Write) | `scripts/lint-page.mjs` | Lint op de zojuist bewerkte pagina; blokkeert nooit |
| `Stop` | `scripts/session-end.mjs` | Ververst `wiki/.graph.json` als er wiki-pagina's gewijzigd zijn |

## Frontend / GitHub Pages

De wiki wordt met **Quartz v4** gepubliceerd op `businessdatasolutions.github.io/ev-wiki`, bij
elke push naar `main` (`.github/workflows/deploy.yml`; Pages-bron: "GitHub Actions").

- Bron: `wiki/` (`npx quartz build -d wiki`). `raw/` staat in `ignorePatterns` en wordt niet
  als pagina gepubliceerd, maar staat wél in de publieke repo.
- Lokaal: `npm ci` en dan `npm run serve` → `http://localhost:8080`.
- Eigen extensies in `extensions/`: typetags, aliassen in de zoekindex, backlinks via aliassen,
  banner bij `status: stale`, zekerheidsregel onder de titel, **▶ Bekijk op YouTube** bij een
  YouTube-`url:`, en het relatiepaneel onder de tekst.

**Auteursrecht.** De repo is publiek, dus de transcripts in `raw/videos/` zijn openbaar, zoals
in de ai-wiki. Wiki-pagina's citeren kort en in eigen woorden, met kanaal en tijdstempel, en
linken naar de video. Hele passages overnemen doen we niet.

## Naslag

- `llm-wiki.md`: het oorspronkelijke concept.
- `llm-wiki-v2.md`: de uitbreiding (levenscyclus, graaf, hooks, zoeken).
- De ai-wiki (`businessdatasolutions/ai-wiki`) voor de uitgebreide redenering achter elke regel
  hierboven; deze wiki neemt de regels over, niet de geschiedenis.
