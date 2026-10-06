---
name: iterative-wiki-query
description: Voer een 4-niveau diepte-zoektocht door de ev-wiki uit voor research-gedreven antwoorden met traceerbare bronvermelding. Gebruik wanneer een vraag context vereist uit meerdere wiki-pagina's — voor LinkedIn-content, syntheses, vergelijkingen, of analyses waar oppervlakkige antwoorden tekortschieten. Produceert een gesynthetiseerd antwoord plus een apart opgeslagen research log in inspiration/.
argument-hint: "<onderwerp of vraag>"
---

# Iteratieve wiki-query (4-niveau diepte-zoektocht)

Een methodische zoektechniek die de ev-wiki gebruikt zoals hij bedoeld is:
beginnen bij `wiki/index.md`, drillen in pagina's, recursief vragen genereren tot
de bronnen op zijn, en alles documenteren zodat elk citaat traceerbaar blijft.

## Wanneer toepassen

Toepassen wanneer:
- De vraag van de gebruiker meerdere wiki-pagina's raakt (concepten + sources + entities).
- De gebruiker iets vraagt over een onderwerp waar de wiki bewijs voor zou moeten hebben.
- Output later gebruikt wordt voor publicatie (LinkedIn, presentaties, syntheses) en
  bronvermelding daarom belangrijk is.
- De gebruiker expliciet vraagt om "diepgang", "research", "wiki bevragen",
  "iteratieve query", of een vergelijkbare formulering.

Niet toepassen voor:
- Triviale lookups van één feit.
- Vragen die buiten de wiki-scope vallen (geen relevante bronnen aanwezig).
- Schrijftaken zonder onderzoeksbehoefte.

## De structuur

```
Niveau 0:  3 startvragen formuleren over het onderwerp
   ↓
Niveau 1:  uit wiki/index.md de meest waarschijnlijke pagina's selecteren
          → openen, lezen, antwoorden onthouden
          → per pagina 3 nieuwe vragen genereren
   ↓
Niveau 2:  per nieuwe vraag de meest waarschijnlijke link kiezen
          → openen, lezen, antwoorden onthouden
          → 3 nieuwe vragen genereren
   ↓
Niveau 3:  laatste keer links volgen, antwoorden onthouden
   ↓
Synthese:  alle verzamelde antwoorden → gesynthetiseerd antwoord
   ↓
Log:       volledige query-trace apart opslaan in inspiration/
```

## Stap 1 — Onderwerp scherp krijgen

Het onderwerp komt binnen via `$ARGUMENTS`, een expliciete vraag, of impliciet uit
de conversatie. Voor je begint:

- Formuleer het onderwerp in één zin.
- Bepaal het beoogde output-formaat (LinkedIn-post / synthese / vergelijking /
  briefing / iets anders). Vraag het de gebruiker als het niet helder is.
- Bepaal of het een **enkelvoudige** query is of dat er **meerdere parallelle
  varianten** nodig zijn (bv. drie LinkedIn-versies vanuit één onderwerp). Bij
  meerdere varianten: voer Niveau 0–3 voor elke variant los uit.

## Stap 2 — Niveau 0: drie startvragen

Formuleer **precies drie** startvragen die samen het onderwerp afdekken vanuit
verschillende invalshoeken. Goede startvragen:

- Beslaan elk een verschillend aspect (oorzaak / omvang / mechanisme; of wat / wie /
  hoe; of probleem / bewijs / oplossing).
- Zijn open genoeg om meerdere bronnen te activeren maar concreet genoeg om
  pagina's gericht te kiezen.
- Worden geëindigd met een vraagteken en geformuleerd in het Nederlands.

Schrijf de drie vragen genummerd op, in een blok dat later in het log komt.

## Stap 3 — Niveau 1: pagina's uit `wiki/index.md`

Lees `wiki/index.md` in één keer. Identificeer **per startvraag** de 1–3 meest
waarschijnlijke pagina's. Selecteer in totaal maximaal 3–4 unieke pagina's voor
Niveau 1 (sommige pagina's beantwoorden meerdere vragen).

Voorkeursvolgorde bij selectie:
1. Concept-pagina's (`wiki/concepts/...`) — als de vraag conceptueel is.
2. Synthese-pagina's (`wiki/syntheses/...`) — als de vraag al beantwoord is in een eerdere synthese.
3. Source-pagina's (`wiki/sources/...`) — voor specifieke claims, cijfers, quotes.
4. Entity-pagina's (`wiki/entities/...`) — alleen als de vraag over een persoon/organisatie gaat.

Lees alle geselecteerde pagina's parallel (één tool-bericht met meerdere Read-aanroepen).

Voor elke pagina: noteer in het log
- Welke startvraag (Q1/Q2/Q3) deze pagina beantwoordt.
- Het kernantwoord — concreet, met cijfers/quotes waar relevant.
- Bronvermelding (auteur + jaar + publicatie als die in de pagina staan).

Genereer dan **per gelezen pagina precies drie nieuwe vragen** (1.1, 1.2, 1.3 voor
pagina 1; 2.1, 2.2, 2.3 voor pagina 2; enz.). Vragen moeten:
- Gaan over iets dat de pagina noemt maar niet uitwerkt.
- Geadresseerd kunnen worden door een gelinkte pagina (kijk welke `[[wikilinks]]`
  in de body staan).

## Stap 4 — Niveau 2: links volgen

Voor elke Niveau-1 vraag: kies de meest waarschijnlijke vervolg-link uit dezelfde
pagina-body. Sommige links komen meerdere keren terug — dat is een sterk signaal.

Selecteer maximaal 3–4 unieke pagina's voor Niveau 2 (clustering is OK). Lees ze
parallel.

Per pagina: noteer kernantwoorden gekoppeld aan de Niveau-1 vragen die ze
beantwoorden (1.1 / 2.3 / 3.2 etc.). Genereer dan opnieuw **drie nieuwe vragen
per pagina** voor Niveau 3.

## Stap 5 — Niveau 3: laatste links

Volg een laatste ronde links. Dit niveau mag korter zijn — je leest niet
noodzakelijk nieuwe pagina's; vaak vinden de Niveau-3 antwoorden in eerder gelezen
pagina's onder secties die je in eerdere niveaus had overgeslagen. Als je nieuwe
pagina's leest, hou het tot maximaal 2–3.

Het is OK om Niveau 3 verkort uit te voeren als de bronnenruimte uitgeput raakt.
Documenteer expliciet waar Niveau 3 minder diep ging.

## Stap 6 — Synthese

Gebruik **alle** verzamelde antwoorden om de output te genereren. De synthese:
- Citeert tenminste 3 verschillende wiki-pagina's.
- Bevat concrete cijfers, quotes, of casussen (geen vage paraphrases).
- Vermeldt auteurs/jaar/publicatie lichtgewicht in de tekst zelf — geen formele
  citaties.
- Volgt het door de gebruiker gevraagde formaat (LinkedIn / synthese / etc.).

## Stap 7 — Research log apart opslaan

Schrijf het **volledige log** weg naar `inspiration/<datum>-<slug>-research-log.md`.

Bestandsstructuur:

~~~markdown
---
type: research-log
topic: "<onderwerp in één zin>"
date: YYYY-MM-DD
output_target: "<bv. LinkedIn-post MKB-MT>"
related_output: "<pad naar uiteindelijke output, indien apart>"
---

# Research log — <onderwerp>

## Niveau 0 — startvragen
1. ...
2. ...
3. ...

## Niveau 1 — pagina's uit index.md

Geselecteerd:
- `wiki/...md` — voor Q...
- `wiki/...md` — voor Q...

### Antwoorden
- **Q1**: ...
- **Q2**: ...
- **Q3**: ...

### Niveau-1 vragen
Van <pagina>: 1.1 ... 1.2 ... 1.3 ...
Van <pagina>: 2.1 ... 2.2 ... 2.3 ...

## Niveau 2 — links gevolgd

Geselecteerd:
- `wiki/...md` — voor 1.1 + 2.3
- ...

### Antwoorden
- **1.1**: ...
- **2.3**: ...

### Niveau-2 vragen
A1 ... A2 ... A3 ...
B1 ... B2 ... B3 ...

## Niveau 3 — laatste links

(Eventueel verkort. Documenteer waarom als je hem korter houdt.)

## Synthese

Kern-elementen die in de output zijn verwerkt:
- ...
- ...

## Bronnenmatrix

| Wiki-pagina | Gebruikte claim |
| ----------- | --------------- |
| ... | ... |
~~~

Bij meerdere parallelle varianten (bv. drie LinkedIn-versies): voeg per variant
een eigen `## Variant <naam>` sectie binnen één enkel research-log toe — niet
drie aparte bestanden.

## Stap 8 — Output-bestand schrijven

Schrijf de synthese (uitkomst van Stap 6) naar het door de gebruiker gevraagde
locatie. Voor LinkedIn-content is de conventie `inspiration/linkedin-post-<persona>-<onderwerp>.md`.

Verwijs in het log (`related_output:`) naar het output-bestand zodat beide aan
elkaar gekoppeld zijn.

## Kwaliteitseisen

Een goed uitgevoerde query voldoet aan:

- [ ] Drie startvragen op Niveau 0 — geen meer, geen minder.
- [ ] Niveau 1 raadpleegt minstens 2 verschillende pagina-types (concept + source,
      of source + synthese).
- [ ] Niveau 2 + 3 voegen nieuwe cijfers, quotes, of casussen toe — geen herhaling
      van Niveau 1.
- [ ] Synthese citeert minstens 3 wiki-pagina's.
- [ ] Research log staat in `inspiration/` met datum-prefix.
- [ ] Bronnenmatrix verbindt elke claim aan een wiki-pagina.

## Veelgemaakte fouten

- **Te brede pagina-selectie op Niveau 1.** Beperk tot 3–4 pagina's; meer leidt tot
  oppervlakkige scans in plaats van diep lezen.
- **Vragen die zichzelf herhalen tussen niveaus.** Elke nieuwe vraag moet iets
  vragen wat het vorige niveau niet heeft beantwoord.
- **Synthese zonder cijfers.** Als de wiki cijfers heeft (en die heeft hij vaak),
  moeten ze in de output landen.
- **Log vergeten.** Dit is een verplichte stap, niet optioneel — de hele waarde van
  de skill zit in traceerbaarheid.
- **Niveau 3 forceren wanneer de bronnen op zijn.** Beter expliciet documenteren
  dat Niveau 3 verkort is dan zwakke vragen verzinnen.

## Voorbeeld-uitvoer (precedent)

Zie [`inspiration/linkedin-post-mkb-mt-wiki-harness.md`](../../../inspiration/linkedin-post-mkb-mt-wiki-harness.md)
voor de eerste volledige toepassing van deze skill: drie LinkedIn-varianten op
basis van 4-niveau queries, met research log en bronnenmatrix in hetzelfde bestand
(uit pre-skill periode — vanaf nu split log + output in twee bestanden).
