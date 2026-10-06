---
type: entity
kind: model
merk: dongfeng
plinkie_pad: ""
aliases: ["Dongfeng Box", "Box", "Nammi Box", "Nammi 01"]
tags: [dongfeng, stadsauto, b-segment, lfp]
confidence: 0.8
last_confirmed: "2026-10-06"
accessed_at: "2026-10-06"
source_count: 2
relationships:
  - type: part-of
    target: dongfeng
  - type: uses
    target: lfp-accu
  - type: competes-with
    target: leapmotor-t03
    via: "ANWB 15-11-2024 (0:00): rechtstreekse vergelijkingstest van twee Chinese stadsauto's onder € 25.000"
    confidence: 0.8
  - type: competes-with
    target: dacia-spring
    via: "ANWB 15-11-2024 (21:28): elektrisch onder € 25.000, de Spring aan de goedkope kant"
  - type: competes-with
    target: citroen-e-c3
    via: "ANWB 15-11-2024 (21:28): elektrisch onder € 25.000; Autovisie 18-09-2024 (7:19): beoogde tegenhanger in een dubbeltest"
    confidence: 0.75
  - type: competes-with
    target: hyundai-inster
    via: "Autovisie 18-09-2024 (2:19): B-segment, de Inster iets hoger geprijsd"
  - type: competes-with
    target: fiat-grande-panda
    via: "Autovisie 18-09-2024 (7:19): beoogde tegenhanger in een dubbeltest ('Panda')"
---

# Dongfeng Box

Elektrische stadsauto van [[dongfeng|Dongfeng]], in China verkocht als Nammi. Geïmporteerd door
[[gomes|Gomes]]. Twee bronnen: een eerste kennismaking van [[autovisie|Autovisie]]
([[2024-09-18-deze-goedkope-chinese-ev-is-europese-concurrentie-te-slim-af|september 2024]]) en een
vergelijkingstest van [[anwb|ANWB]] tegen de [[leapmotor-t03|Leapmotor T03]]
([[2024-11-15-chinese-evs-onder-de-25-mille-kleine-autos-grote-verleiding|november 2024]]), die
elkaar op accu's, garantie, trekgewicht en importeur bevestigen.

**Plinkie.** Nog niet gekoppeld: het pad op Plinkie is niet nagegaan.

## Uitvoeringen

| Accu | Bereik (fabriek) | Opmerking |
| --- | --- | --- |
| 31,5 kWh (Autovisie: "ongeveer 32") | 230 km | goedkopere uitvoering, aangekondigd voor 2025; mist stoelverwarming en -ventilatie, elektrische spiegels, lichtmetalen velgen en vehicle-to-load |
| 42,5 kWh (Autovisie: "ongeveer 42") | 310 km | launch edition, de enige bij opname |

Beide met een [[lfp-accu|LFP-accu]], 95 pk en 160 Nm.

## Fabrieksopgaven

Snelladen 60 kW volgens Autovisie, ook op de instapper; ANWB's waarde is onleesbaar. Gewicht 1350 kg
(ANWB) of 1400 kg (Autovisie). [[trekgewicht|Trekgewicht]] 750 kg (ongeremd volgens Autovisie).
Topsnelheid 140 km/u. Garantie 5 jaar / 100.000 km, accu 8 jaar / 160.000 km. Standaard 360°-camera,
sfeerverlichting, draadloos CarPlay en draadloos laden van de telefoon.

## Metingen

| Tester | Datum | Uitvoering | Omstandigheden | Verbruik | Bereik | Fabriek |
| --- | --- | --- | --- | --- | --- | --- |
| ANWB | 15-11-2024 | 42,5 kWh | 7 °C, weinig wind, snelweg en binnendoor | 15,3 kWh/100 km | **250–300 km** (afgeleid) | 310 km |

Bron: [[2024-11-15-chinese-evs-onder-de-25-mille-kleine-autos-grote-verleiding|ANWB, 14:18]]. Zie
[[praktijkbereik]]. Thuisladen gaat op één fase: na 9 uur nog niet vol ([[eenfase-laden]]).

## Valkuilen

- **Geen laadkabel** in de standaarduitrusting.
- **Eén fase thuisladen** ([[eenfase-laden]]).
- **Laadtijd opgegeven als 30–80%** in plaats van 10–80% (Autovisie); zie [[snelladen-10-80]].
- **Geen dode-hoekwaarschuwing en geen waarschuwing voor kruisend verkeer**, terwijl de T03 de eerste wel heeft.
- **[[kofferbakinhoud|Kofferbak]]** 326 L (945 L met de bank plat), maar geen vlakke laadvloer, een
  hoge tildrempel en een smalle opening; geen frunk.
- Geen achterruitwisser, geen ventilatie of USB/stroompunt achterin.

## Oordelen

- **Onderstel**: comfortabel in de stad (Autovisie), maar stug en springerig op korte oneffenheden (ANWB).
- **Besturing**: zonder gevoel en sterk bekrachtigd (Autovisie); reageert te traag (ANWB).
- **Interieur**: goede bouwkwaliteit en zachte materialen (beide); infotainment als een Android-tablet,
  CarPlay koppelen via een aparte app.
- **Geluid**: fluittoon en hoorbare banden (ANWB).
- **Eindoordeel**: "heel sterk aanbod" (Autovisie); ruimer, zuiniger en meer garantie dan de T03, maar
  weinig servicepunten en onbekende restwaarde (ANWB).

## Concurrenten

| Model | Wie | Grond |
| --- | --- | --- |
| [[leapmotor-t03|Leapmotor T03]] | ANWB | rechtstreekse vergelijkingstest |
| [[citroen-e-c3|Citroën ë-C3]] | ANWB, Autovisie | onder € 25.000; beoogde tegenhanger in een dubbeltest |
| [[dacia-spring|Dacia Spring]] | ANWB | onder € 25.000, de goedkope kant |
| [[hyundai-inster|Hyundai Inster]] | Autovisie | B-segment, iets duurder |
| [[fiat-grande-panda|Fiat Grande Panda]] | Autovisie | beoogde tegenhanger ("Panda") |

De ë-C3 is het enige paar dat twee bronnen noemen.

## Weergaven

| Bron | Gemeten | Aantal | Per dag |
| --- | --- | --- | --- |
| Autovisie, 18-09-2024 | 06-10-2026 | 31.788 | 42 |
| ANWB, 15-11-2024 (vergelijkingstest, telt ook voor de T03) | 06-10-2026 | 68.599 | 99 |

Verschillende kanalen, dus niet onderling te vergelijken.

## Debatten en vervanging

- **Gewicht**: 1350 kg (ANWB) tegen 1400 kg (Autovisie). Klein verschil, mogelijk een andere
  uitvoering of afronding.
- **Snelladen**: Autovisie noemt 60 kW; ANWB's getal is in het transcript onleesbaar ("87 pro8 KW").
  Te controleren bij de fabrikant.
- **Uitrusting**: Autovisie reed een preproductie-auto; de rijhulpsystemen zijn alleen door ANWB beoordeeld.
