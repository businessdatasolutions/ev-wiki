# Log

Logboek van de bewerkingen op deze wiki, **nieuwste bovenaan**. Nieuwe regels komen direct onder de `---` hieronder. Vast formaat, zodat `grep "^## \[" wiki/log.md | head -10` de tien laatste geeft:

    ## [JJJJ-MM-DD] <op> | <titel>

Toegestane bewerkingen: `ingest`, `acquire`, `query`, `lint`, `synthesize`, `refactor`, `bulk-refactor`.

---

## [2026-10-06] acquire | verzamelaar: 6 review(s)

Opgehaald door `onderzoek/verzamelaar.py`, nog niet verwerkt (wacht op Process):

- `raw/videos/deze-nieuwe-bmw-3-serie-is-totaal-anders-dan-de-i3-andere-verhoudingen-met-vier-en-zescili.md` (AutoWeek; bmw/i3)
- `raw/videos/de-volkswagen-id-tiguan-is-meer-dan-een-simpel-opgefriste-id4-andere-opzet-technisch-wel-g.md` (AutoWeek; volkswagen/id-4)
- `raw/videos/de-peugeot-e-208-gti-is-de-meest-waardige-opvolger-van-de-205-gti-hele-berg-rijplezier.md` (AutoWeek; peugeot/e-208-gti)
- `raw/videos/de-mg-im5-heeft-veel-te-bieden-maar-daar-betaal-je-dan-ook-voor-groter-maar-duurder-dan-mo.md` (AutoWeek; mg/mg-im5)
- `raw/videos/de-skoda-peaq-is-heel-fijn-en-niet-vatbaar-voor-de-pseudo-eindheffing-groter-en-luxer-een.md` (AutoWeek; skoda/peaq)
- `raw/articles/anwb-auto-review-toyota-c-hr-i.md` (ANWB; toyota/c-hr-plus)

## [2026-10-06] acquire | verzamelaar: 5 review(s)

Opgehaald door `onderzoek/verzamelaar.py`, nog niet verwerkt (wacht op Process):

- `raw/articles/anwb-auto-review-mercedes-c-klasse-vi-w520.md` (ANWB; mercedes-benz/c-klasse-limousine)
- `raw/articles/anwb-de-10-elektrische-auto-s-met-de-grootste-actieradius.md` (ANWB; artikel)
- `raw/articles/anwb-top-10-goedkoopste-elektrische-auto-s.md` (ANWB; artikel)
- `raw/articles/anwb-garantie-op-elektrische-auto-en-accupakket.md` (ANWB; artikel)
- `raw/articles/anwb-welke-nieuwe-elektrische-auto-s-komen-er-in-2026.md` (ANWB; artikel)

## [2026-10-06] acquire | verzamelaar: 9 review(s)

Opgehaald door `onderzoek/verzamelaar.py`, nog niet verwerkt (wacht op Process):

- `raw/videos/rijtest-mazda-cx-6e-dit-is-veel-beter-dan-6e.md` (Autovisie; mazda/cx-6e)
- `raw/articles/anwb-auto-review-leapmotor-b05-i.md` (ANWB; leapmotor/b05)
- `raw/articles/anwb-auto-review-volvo-ex60-i.md` (ANWB; volvo/ex60)
- `raw/articles/anwb-auto-review-alpine-a390-i.md` (ANWB; alpine/a390)
- `raw/articles/anwb-auto-review-volkswagen-id-polo-i.md` (ANWB; volkswagen/id-polo)
- `raw/articles/anwb-auto-review-toyota-bz4x-i-1e-facelift.md` (ANWB; toyota/bz4x)
- `raw/articles/anwb-auto-review-nissan-leaf-iii.md` (ANWB; nissan/leaf)
- `raw/articles/anwb-9-elektrische-auto-s-met-trekhaak.md` (ANWB; artikel)
- `raw/articles/anwb-top-10-elektrische-caravantrekkers.md` (ANWB; artikel)

## [2026-10-06] ingest | Tweede batch: 9 reviews, waarvan 8 van de verzamelaar, verwerkt door parallelle subagents

Negen bronnen, elk door een eigen subagent tot concept-bronpagina en voorstel verwerkt, daarna in één pass samengevoegd (zodat gedeelde pagina's één keer geschreven worden):

- [[2026-10-02-bmw-ix3-vs-volvo-ex60-roadtrip-met-special-guest]] (ANWB, vergelijkingstest, plus de Mercedes GLC)
- [[2026-09-26-waarom-wij-voor-de-peugeot-e-208-gti-zouden-kiezen]] (Autovisie)
- [[2026-09-13-skoda-epiq-troeft-zelfs-volkswagen-id-polo-af]] (Autovisie, met meting)
- [[2026-09-11-rijtest-in-een-rationele-wereld-zou-iedereen-leapmotor-b03x-rijden]] (Autovisie)
- [[2026-09-10-geliefd-in-nederland-populaire-volvo-xc40-en-ex40-weer-gefacelift]] (Autovisie, nieuws met fabrieksopgaven)
- [[2026-09-09-is-de-volkswagen-id-polo-de-nieuwe-publiekslieveling]] (ANWB, met meting)
- [[2026-09-06-elektrische-sportwagens-voor-weinig-de-audi-e-tron-gt-en-porsche-taycan-zijn-flink-afgesch]] (Autovisie, occasiontest)
- [[2026-07-27-elektrische-c-klasse-doet-het-heel-anders-dan-de-bmw-i3]] (Autovisie, met meting)
- AutoWeek, ID. Polo tegen Renault 5 (vergelijkingstest; met de hand opgehaald op aanwijzing van de eigenaar)

Besluiten bij het samenvoegen:
- **Een vergelijking is concurrentie** (besluit eigenaar): modellen van verschillende merken in een vergelijkingsvideo zijn elkaars concurrent; `vergelijking: true` op de bron, lint controleert de paren. Ook gezet op de Box-tegen-T03-test van ANWB.
- Opel Corsa GSE en Lancia Ypsilon HF zijn uitvoeringen van `opel-corsa-electric` en `lancia-ypsilon`, de paden die Plinkie heeft.
- `accugezondheid` niet als concept opgenomen: gaat over tweedehands, Plinkie vergelijkt nieuwe lease.
- Nieuwe concepten: voorconditioneren, wegenbelasting, bidirectioneel laden.

Bevindingen:
- De titel stuurt de verzamelaar soms naar de concurrent: "Elektrische C-klasse doet het heel anders dan de BMW i3" gaat over de Mercedes; de controle bij Process ving het op.
- Eerste tegenspraak tussen bronnen: kofferbak Škoda Epiq 490 L (ANWB) tegen ruim 470 L (Autovisie).
- Volvo hernoemde alleen de aandrijflijnen (Single Motor → P5, Twin Motor → P8 AWD); Plinkie kent de EX40 ook als `xc40-recharge`.
- Weergaven verschillen per soort video: een Occasion Battle van Autovisie haalt 5.507 per dag tegen 42 voor een eerste kennismaking. Binnen één kanaal vergelijken is niet genoeg.

## [2026-10-06] acquire | verzamelaar: 8 review(s)

Opgehaald door `onderzoek/verzamelaar.py`, nog niet verwerkt (wacht op Process):

- `raw/videos/bmw-ix3-vs-volvo-ex60-roadtrip-met-special-guest.md` (ANWB; bmw/ix3, volvo/ex60)
- `raw/videos/is-de-volkswagen-id-polo-de-nieuwe-publiekslieveling-anwb-autotest.md` (ANWB; volkswagen/id-polo)
- `raw/videos/waarom-wij-voor-de-peugeot-e-208-gti-zouden-kiezen.md` (Autovisie; peugeot/e-208-gti)
- `raw/videos/skoda-epiq-troeft-zelfs-volkswagen-id-polo-af.md` (Autovisie; skoda/epiq, volkswagen/id-polo)
- `raw/videos/rijtest-in-een-rationele-wereld-zou-iedereen-leapmotor-b03x-rijden.md` (Autovisie; leapmotor/b03x)
- `raw/videos/geliefd-in-nederland-populaire-volvo-xc40-en-ex40-weer-gefacelift.md` (Autovisie; volvo/ex40)
- `raw/videos/elektrische-sportwagens-voor-weinig-de-audi-e-tron-gt-en-porsche-taycan-zijn-flink-afgesch.md` (Autovisie; audi/e-tron)
- `raw/videos/elektrische-c-klasse-doet-het-heel-anders-dan-de-bmw-i3-dit-is-echt-goed.md` (Autovisie; bmw/i3)

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
