---
title: "Filtermodel van Plinkie (momentopname 06-10-2026)"
author: ["Plinkie"]
url: "https://plinkie.nl"
date_published: 2026-10-06
notes: |
  Momentopname van wat een bezoeker van plinkie.nl kan kiezen en waarop hij kan sorteren,
  opgeschreven op 06-10-2026 door Claude uit de werking van de site. Bevat alleen wat op de
  site zichtbaar is: geen interne bronnenlijst en geen code.
---

# Filtermodel van Plinkie

Plinkie (plinkie.nl) vergelijkt private lease van elektrische auto's. De kiezer op de voorpagina
leest één vraag: welke auto's, voor hoeveel kilometer per jaar, voor hoe lang.

## Vraag

- **Kilometers per jaar.** In klassen van 5.000 km. Standaard 10.000 km.
- **Looptijd.** In maanden. Standaard 60 maanden.

## Filters (facetten)

| Filter | Waarden |
| --- | --- |
| Carrosserie | De vorm die de aanbieder opgeeft, met spelling samengevoegd: SUV (ook "Sports Utility Vehicle"), Hatchback, Stationwagen, Cabriolet, Sedan, MPV. Andere waarden blijven zoals de bron ze schrijft. Een auto zonder opgegeven carrosserie valt onder "niet vermeld". |
| Merk | Het merk, met één vaste schrijfwijze per merk (diakriet wint: "Citroën"). |
| Model | `<merk>/<model>` zoals het pad van de modelpagina (`/deals/<merk>/<model>`). Meerdere modellen tegelijk kiezen kan: een shortlist. |
| Prijs | Prijsklassen van € 200 per maand (bijv. "€ 400 – € 599"). Auto's zonder één gepubliceerde prijs vallen in een eigen klasse. |
| Aanbieder | De leasemaatschappij of het merkprogramma dat de aanbieding doet. |

## Sorteringen

| Sortering | Richting standaard | Toelichting |
| --- | --- | --- |
| EerlijkePrijs | van goedkoop naar duur | Plinkie's eigen, publiek nagerekende maandprijs met de bijkomende kosten erin |
| Rijbereik (WLTP) | van ver naar kort | de opgave van de aanbieder of fabrikant |
| Snelladen 10–80% | van snel naar traag | laadtijd in minuten aan een snellader |
| Merk | A–Z | |
| Model | A–Z | |

Een auto waarvan een waarde onbekend is, staat bij elke richting achteraan. Bij gelijke waarden
beslist een vaste sleutel, zodat dezelfde vraag altijd dezelfde volgorde geeft.

## Velden per auto die de site kent

Rijbereik (km), verbruik (kWh/100 km), laadtijd AC en DC (min), carrosserie, zitplaatsen, deuren,
transmissie, maandbedrag, looptijd, kilometerbundel, EerlijkePrijs.

## Wat er niet in zit

Geen filter op trekhaak of trekgewicht, één of drie fasen thuisladen, warmtepomp, kofferbakinhoud
of laadkabel inbegrepen. Zulke kenmerken noemen testers wel.
