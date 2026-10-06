# EV-Wiki

Een kennisbank over elektrische auto's, opgebouwd en bijgehouden door een taalmodel uit reviews,
tests en artikelen. Gepubliceerd met [Quartz v4](https://quartz.jzhao.xyz/).

Lees de site: **[businessdatasolutions.github.io/ev-wiki](https://businessdatasolutions.github.io/ev-wiki)**

## Wat erin staat

Per model: wat de fabrikant opgeeft, wat testers **zelf meten** (verbruik, bereik bij welke
temperatuur), welke **valkuilen** per uitvoering de configurator niet noemt (een kofferbak die alleen
met losse stoelen klopt, een auto zonder trekhaak, thuisladen op één fase), wat testers vinden, en
**met welke modellen testers hem vergelijken**. Elk feit linkt naar het moment in de video of de
plek in het artikel waar het vandaan komt.

De wiki is werkmateriaal voor [Plinkie](https://plinkie.nl), de vergelijker van private lease voor
elektrische auto's.

## Hoe het werkt

Het patroon is Andrej Karpathy's [LLM Wiki](llm-wiki.md): in plaats van bij elke vraag opnieuw in
ruwe bronnen te zoeken, verwerkt een taalmodel elke nieuwe bron één keer in een blijvende,
onderling gelinkte wiki. Het systeem (levenscyclus van beweringen, getypeerde relaties, retentie,
kwaliteitsscore, lokaal zoeken, hooks) komt uit de
[ai-wiki](https://github.com/businessdatasolutions/ai-wiki). De werkwijze staat in [CLAUDE.md](CLAUDE.md).

```
raw/      ruwe bronnen (transcripts, artikelen), onveranderlijk
wiki/     sources/ · entities/ (modellen, merken, kanalen) · concepts/ · syntheses/ · threads/
scripts/  lint, graaf, kwaliteit, zoeken
```

## Lokaal

```sh
npm ci
npm run serve   # http://localhost:8080
```

## Auteursrecht

De transcripts in `raw/videos/` zijn van de makers van de video's. Wiki-pagina's vatten samen in
eigen woorden, citeren kort, en linken naar het moment in de video.
