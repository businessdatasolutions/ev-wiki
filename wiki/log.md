# Log

Logboek van de bewerkingen op deze wiki, **nieuwste bovenaan**. Nieuwe regels komen direct onder de `---` hieronder. Vast formaat, zodat `grep "^## \[" wiki/log.md | head -10` de tien laatste geeft:

    ## [JJJJ-MM-DD] <op> | <titel>

Toegestane bewerkingen: `ingest`, `acquire`, `query`, `lint`, `synthesize`, `refactor`, `bulk-refactor`.

---

## [2026-10-06] ingest | Eerste batch: Plinkie-filtermodel, Kia EV2 (ANWB), Box tegen T03 (ANWB), Dongfeng Box (Autovisie)

Eerste ingest na het opzetten van de wiki. Vier bronnen:

- [[2026-10-06-plinkie-filtermodel]]: de woorden van Plinkie. Werd zeven concepten (carrosserie, prijsklasse, EerlijkePrijs, rijbereik WLTP, snelladen 10–80%, kilometerbundel, looptijd).
- [[2026-04-01-grote-actieradius-en-goed-rijgedrag-voor-nieuwe-kia-ev2]], [[2024-11-15-chinese-evs-onder-de-25-mille-kleine-autos-grote-verleiding]] en [[2024-09-18-deze-goedkope-chinese-ev-is-europese-concurrentie-te-slim-af]]: drie reviews, opgehaald met `--sub-lang nl`.

Nieuwe pagina's: 3 modelpagina's (Kia EV2, Leapmotor T03, Dongfeng Box), 11 korte modelpagina's voor genoemde concurrenten, 13 merken, 2 concerns (Stellantis, Volkswagen-groep), 2 kanalen (ANWB met `ook_aanbieder`, Autovisie), ANWB Private Lease, Gomes, Plinkie, en 15 concepten.

Buurbronnen: ANWB-vergelijking `supports` Autovisie (zelfde Box). Concurrentie: 17 `competes-with`-randen op de drie modelpagina's. Het enige paar met twee bronnen is Dongfeng Box en Citroën ë-C3.

Bevindingen tijdens de ingest:
- Het transcriptpaneel gaf de Autovisie-video in het Engels; `--sub-lang` toegevoegd aan de skill.
- De eerste VTT-parser liet zinnen vallen bij een regel met alleen een spatie; herschreven, met test.
- Alle prijzen in de ANWB-vergelijking en de Autovisie-video zijn onleesbaar in het transcript en staan nergens in de wiki.
