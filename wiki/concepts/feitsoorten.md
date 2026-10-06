---
type: concept
aliases: ["feitsoort"]
tags: [feitsoorten]
confidence: 0.85
last_confirmed: "2026-10-06"
accessed_at: "2026-10-06"
source_count: 4
quality_score: 1
---

# Feitsoorten

De gesloten lijst waarmee elke bronpagina zegt **wat voor feiten** ze over een auto levert. Dit is de
enige plek waar de lijst staat; `scripts/lint-page.mjs` controleert ertegen.

| Feitsoort | Wat het is | Voorbeeld uit de wiki |
| --- | --- | --- |
| `fabrieksopgave` | wat de fabrikant publiceert, ook als de tester het herhaalt: accu, WLTP, vermogen, prijs | 453 km voor de [[kia-ev2|Kia EV2]] met 61 kWh |
| `meting` | wat de tester zelf mat, met omstandigheden | 240 km voor de [[leapmotor-t03|Leapmotor T03]] bij 7 °C |
| `valkuil` | wat de keuze verandert en de configurator niet zegt, per uitvoering | 362 L kofferbak in de EV2 met vaste achterbank |
| `oordeel` | de mening van de tester | het stuur van de [[dongfeng-box|Dongfeng Box]] "zonder feedback" |
| `merk-en-service` | dealers, garantie, restwaarde, importeur, crashtest | zes Voyah-vestigingen voor Dongfeng |

**Waarom deze vijf.** Voor [[plinkie|Plinkie]] verschilt de waarde per soort. Een fabrieksopgave heeft
Plinkie al. Een meting en een valkuil zijn wat de fabrikant niet zegt, en dus wat een review toevoegt.
Een oordeel is waardevol maar persoonlijk. Merk en service verandert langzaam en hoort op de merkpagina.

Van de drie reviews op 06-10-2026 heeft alleen [[2024-11-15-chinese-evs-onder-de-25-mille-kleine-autos-grote-verleiding|ANWB, Box tegen T03]] een eigen `meting`; alle drie hebben een
`valkuil`.

## Bronnen

- [[2026-10-06-plinkie-filtermodel|Plinkie-filtermodel]]
- [[2026-04-01-grote-actieradius-en-goed-rijgedrag-voor-nieuwe-kia-ev2|ANWB, Kia EV2]]
- [[2024-11-15-chinese-evs-onder-de-25-mille-kleine-autos-grote-verleiding|ANWB, Box tegen T03]]
- [[2024-09-18-deze-goedkope-chinese-ev-is-europese-concurrentie-te-slim-af|Autovisie, Dongfeng Box]]

## Debatten en vervanging

- Een bron met een belang (ANWB leaset zelf) levert dezelfde soorten feiten; de soort zegt niets over de betrouwbaarheid. Dat regelt `confidence`.
