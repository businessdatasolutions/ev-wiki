---
name: neighbour-source-scan
description: Gebruik bij elke ingest van een nieuwe bron, direct na het invullen van `merken:`, `modellen:` en `feitsoorten:` en vóór het bijwerken van concept- en entiteitspagina's (stap 5 van Process in CLAUDE.md). Ook wanneer de gebruiker vraagt of een verwante bron is gemist. Zoekt bronnen over hetzelfde model of merk, of met dezelfde conceptpagina's, en legt per buur een getypeerde relatie vast.
---

# Buurbronnen zoeken

Stap 5 van Process in `CLAUDE.md`. Twee bronnen over dezelfde auto zonder relatie ertussen is
een gat in de graaf, geen neutrale toestand. Juist bij auto's is de botsing het interessante
deel: de ene tester meet 240 km, de andere 280.

## Drie zoekpaden. Draai ze alle drie

### Pad A: hetzelfde model

Voor elk slug in `modellen:` van de nieuwe bron:

```bash
grep -l "<model-slug>" wiki/sources/*.md
```

Controleer bij elke treffer dat het slug in `modellen:` staat en niet alleen als concurrent in de
tekst. Kijk daarna naar `feitsoorten:`: twee bronnen met allebei `meting` over hetzelfde model
zijn de eerste kandidaten voor `supports` of `contradicts`.

### Pad A2: hetzelfde merk

Voor elk slug in `merken:` dat géén model in deze bron heeft, of als de bron over het merk zelf
iets zegt (dealers, garantie, importeur):

```bash
grep -l "<merk-slug>" wiki/sources/*.md
```

Een zwakkere aanwijzing dan hetzelfde model. Een relatie alleen als beide bronnen iets over het
merk zeggen dat overeenkomt (`supports`) of botst (`contradicts`), bijvoorbeeld het aantal
servicepunten of de garantietermijn.

### Pad B: dezelfde conceptpagina's

Voor elke conceptpagina die je in stap 6 gaat bijwerken (bijv. `praktijkbereik`,
`eenfase-laden`):

```bash
grep -l "\[\[praktijkbereik" wiki/sources/*.md
```

Dit vangt bronnen over een ander model die hetzelfde verschijnsel beschrijven, zoals twee
Chinese stadsauto's die allebei op één fase laden.

## Beslissen per kandidaat

| Situatie | Relatie | `via:` |
|---|---|---|
| Zelfde model, meting of oordeel komt overeen | `supports` | optioneel |
| Zelfde model, getal of oordeel botst | `contradicts` | **verplicht**: waar het op draait (temperatuur, uitvoering, route) |
| Nieuwere review vervangt een oudere over dezelfde uitvoering volledig | `supersedes` | met het supersessieprotocol |
| Zelfde merk, en beide zeggen iets over het merk | `supports` of `contradicts` | verplicht bij `contradicts` |
| Alleen hetzelfde merk zonder gedeelde bewering, of alleen als concurrent genoemd | geen relatie | |

Niet elke gedeelde naam is een relatie. Een review die de Skoda Epiq als concurrent noemt, heeft
geen relatie met een review van de Epiq.

**Let op de uitvoering.** Twee metingen van "de Dongfeng Box" botsen niet als de ene de 31,5 kWh
was en de andere de 42,5 kWh. Zet dat in `via:`, of leg geen `contradicts` vast.

## Vastleggen

Zet de relatie in de frontmatter van de **nieuwe** bron:

```yaml
relationships:
  - type: supports
    target: 2024-11-15-chinese-evs-onder-de-25-mille-kleine-autos-grote-verleiding
    via: "zelfde garantie en accu's, andere tester"
```

En in de tekst als `[[wikilink]]` met één zin uitleg (de lichaamswikilinkregel in `CLAUDE.md`).
De omgekeerde richting hoeft niet: `scripts/graph-export.mjs` rekent die uit.

**Bij drie of meer kandidaten:** noem de lijst in je antwoord aan de gebruiker vóór de commit,
zodat een gemiste buur opvalt.
