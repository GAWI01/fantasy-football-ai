# FPL-AI baseline og helsesjekk

> Historisk dokument (2026-08-28). `healthcheck.py` er fjernet; serveringspakken valideres nå med
> `python -m backend.runtime_artifacts`, og modellen med `python -m historical_data.validate_model`.

Dato: 2026-08-28

## Hva som er verifisert

- `python -m unittest discover -s tests -v`: 4 tester bestått.
- `healthcheck.audit_project(...)`: de tre sentrale current-datafilene har alle 616 rader og identiske `player_id`-sett.
- Helsesjekken kjører 20 ganger på 0,178 sekunder på denne maskinen (ca. 9 ms per kjøring).
- `fpl.db` inneholder tabellene `players` (616 rader), `fixtures` (380 rader) og `player_history` (610 rader).

Helsesjekken er bevisst skrivebeskyttet. Den validerer foreløpig at de operative current-datafilene finnes, har `player_id`, ikke har duplikate ID-er og beskriver samme spillerunivers.

## Bekreftede funn

### P0 - prediksjonsinput er ikke kompatibel med treningsinput

`historical_data/train_model.py` trener på rolling-felter med siste fem gameweeks. `historical_data/current_data/predict_gw.py` gir imidlertid modellen sesongakkumulerte proxyer: `minutes_last_5 = minutes`, `goals_last_5 = goals`, og en `starts_last_5` på 0--1 i stedet for antall starter siste fem. Dette gir modellinput på en annen skala enn treningsdataene.

Konsekvens: `gw2_predictions_v4.csv` kan brukes som et historisk baseline-output, men skal ikke behandles som validert expected points før live-featurebyggingen er felles med treningsfeaturebyggingen.

### P0 - Wildcard V5 har fortsatt kombinatorisk eksplosjon

V5 genererer alle posisjonskombinasjoner før `max_combinations` brukes. Med de hardkodede kandidatgrensene er de rå kombinasjonsmengdene 66 GKP, 142 506 DEF, 324 632 MID og 1 140 FWD. Beam-steget kan deretter forsøke 15 000 × 8 000 = 120 millioner par i ett krysspunkt.

Konsekvens: dette er hovedårsaken til treghet. V5 må ikke benchmarkes som en produksjonskandidat eller utvides; den erstattes av en eksakt ILP/CP-SAT-kjerne i en senere, separat fase.

### P1 - xMins er en GW2-heuristikk, ikke en modell

`players_features_current_v2.csv` har 283 spillere med `VERY_HIGH` rotasjonsrisiko. Median xMins er 10, og høyeste verdi er 82. Verdiene er primært bestemt av minutter i GW1 og FPLs availability-felt, ikke historiske start-/rotasjonsmønstre.

Konsekvens: xMins skal foreløpig brukes som en enkel tilgjengelighetsindikator, ikke som et kalibrert sannsynlighetsestimat.

### P1 - double gameweeks håndteres feil

`predict_gw.py` bruker én dictionary-verdi per lag for neste GW. En ny fixture for samme lag overskriver den første. Double gameweeks får dermed ikke summert fixture- eller poengbidrag korrekt.

### P1 - datalagrene er inkonsistente

CSV-pipelinen og SQLite-databasen er separate. I tillegg kjører `fpl.py` `DELETE FROM player_history` før ny innlasting. Databasen er derfor ikke en varig, versjonert historikk.

### P2 - prosjekthygiene mangler

- Mappen er ikke et Git-repository; det finnes ingen baseline-commit, branch eller worktree.
- Det finnes ingen `requirements.txt`, `pyproject.toml` eller annen dependency-manifest.
- Det fantes ingen testsuite før denne baseline-fasen.
- Optimizer-mappen er tom, mens optimizer-eksperimentene ligger under `historical_data/current_data/`.

## Ikke kjørt med vilje

Skript som skriver eller sletter data ble ikke brukt i baselinen, inkludert FPL-oppdatering, historikknedlasting, prediksjonsgenerering og Wildcard V5. Dette beskytter gjeldende data og unngår å forveksle en miljø-/datamutering med baseline-resultater.

## Beslutning for neste fase

Grunnmuren er dokumentert, men ikke produksjonsklar. Neste arbeid bør fortsatt være grunnmur: etablere avhengighetsmanifest, kjørbar prosjektkommando, konsekvente data- og featurekontrakter og utvidede integritetstester. Optimizer og nye football-features skal ikke påbegynnes før dette er grønt.
