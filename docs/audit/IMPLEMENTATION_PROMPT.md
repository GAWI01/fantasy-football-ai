# Implementeringsprompt: Football Fantasy AI, korrekthet og pålitelighet

Du er senior full-stack- og ML-utvikler på Football Fantasy AI (`GAWI01/fantasy-football-ai`). Stacken er FastAPI i `backend/`, beslutningsmoduler i roten og i `optimizer/`, og Next.js i `frontend/`.

En praktisk ende-til-ende-audit (`docs/audit/PRACTICAL_PRODUCT_AUDIT_2026-10-11.md`) kjørte appen mot ekte FPL-data og 12 ekte lag. Alle funnene under er reprodusert. Les rapporten først. Ikke implementer noe som ikke står her uten å påvise problemet først.

## Rammer

- Behold arkitekturen: FastAPI, Next.js, CSV- og manifest-serving, MILP via SciPy, envelope-kontrakten (`data`/`meta`/`errors`) og designspråket i frontend. Ingen redesign, ingen nye rammeverk, ingen nye avhengigheter uten sterk grunn.
- Ingen endring av modellartefakter eller sertifisering uten å kjøre `python -m historical_data.validate_model`.
- Hver endring skal ha tester som **feiler før** og **passerer etter** endringen.
- Etter hver fase skal disse være grønne:
  - `python -m pytest tests backend/tests`
  - `cd frontend && pnpm test && pnpm lint && pnpm exec tsc --noEmit && pnpm build`
- **Re-test i runtime etter fixene.** Hvis prognosen ikke matcher neste GW, lag en lokal simulering der bare bootstrap-flaggene `is_current`, `is_next` og `deadline_time` skrives om (se rapporten, «Metode»). Kjør `/api/v1/dashboard/{id}` for minst disse lagene og rapporter før/etter i en tabell (aksjon, transfers, hit, captain, confidence, wildcard):
  - 9100001, 9100002, 9100003
  - 9100004, 9100005
  - 6658075, 9100011, 9100009
  - 9100008, 9100010, 9100006, 9100007

  Test også `?free_transfers=0`, `2` og `3`.

---

## MUST FIX

### M1. XI-bevisst transferverdi (ISSUE-002)

- **Problem:** `transfer_analysis.py:optimize_transfer_plan` maksimerer summen av poeng for alle 15 spillere. Resultatet er at den anbefaler bytte av reservekeeper (Forster 0 xMins → Pickford) og benkoppgraderinger.
- **Endring:**
  - Legg til startvariabler `s_i` med `s_i ≤ x_i`, `Σ s_i = 11` og formasjonsgrenser: GK = 1, DEF 3–5, MID 2–5, FWD 1–3.
  - Objektiv: `Σ s_i·v_i + Σ (x_i − s_i)·v_i·w_bench(pos)`. Bruk `w_bench` som navngitt konstant, ca. 0,1 for utespillere og ca. 0,0–0,03 for GK.
  - `v_i` er den vektede horisontverdien som i dag.
  - Rapporter gevinst som endring i forventet **XI-verdi** (pluss benkvekt), ikke som `in.pp − out.pp`.
  - Behold budsjett, posisjon, maks 3 per klubb, alternativ-genereringen og output-feltene.
- **Tester:** benk-GK-bytte anbefales ikke når GK1 spiller. En ren benkoppgradering har gevinst ≈ `w_bench·Δ`. Eksisterende `tests/test_transfer_optimizer.py` og `tests/test_transfer_decision.py` skal fortsatt passere eller oppdateres med begrunnelse.

### M2. Roll/HOLD som reell beslutning (ISSUE-003)

- **Problem:** Rull-planen har `net=0`, så enhver positiv gevinst vinner. Med FT=2 eller 3 brukes alltid alle.
- **Endring:**
  - Innfør `roll_value(free_transfers_after)` (konstant per banket FT, med maks 5 FT).
  - En plan med k transfers scores som `net_gain(k) + roll_value(FT − k)`. Rull scores som `roll_value(FT)`.
  - Velg maks over k = 0 … FT+2 (se M7).
  - Kalibrer konstanten med `backtesting/decision_backtest.py` hvis mulig. Dokumenter ellers verdien som antakelse i koden.
  - `decision_strategy.choose_transfer_action` returnerer `ROLL`/`HOLD`, `TRANSFER` eller `MULTI_TRANSFER` utelukkende ut fra den valgte planen (antall transfers).
- **Tester:** et sterkt lag der beste gevinst er under rulleverdien gir `HOLD` eller `ROLL`. Med FT=2, én sterk og én marginal gevinst, brukes 1 transfer.

### M3. Én rangering og entydige felt (ISSUE-004)

- **Problem:** `decision_intelligence._select_horizon_transfer` re-rangerer med `combined_score = net_gain (allerede 5-GW-vektet) + horizon_gain (ny minutt-justert 5-GW-sum)`. Det dobbeltteller horisonten, og i 4 av 12 lag gir det en annen plan enn `transfers.recommended_transfers`. Frontend viser intelligence-versjonen (`frontend/lib/model/plan.ts:201-210`).
- **Endring:**
  - Optimereren eier valget.
  - `intelligence.transfer_strategy.selected_transfers` **skal være identisk** med `transfers.recommended_transfers`.
  - Intelligence beregner bare forklaringsmetrikker for den valgte planen og alternativene, i samme rekkefølge som optimereren: `next_gw_gain`, `horizon_gain` (samme vekting som optimereren), `hit_cost` og `net_horizon_gain`.
  - Fjern ekstra minutt-justering (`0,5 + 0,5·xmins/90` i `decision_horizon.player_horizon_projection`). Modell-`predicted_points` inkluderer allerede minutter og tilgjengelighet.
  - Gi feltene nye navn, med bakoverkompatible alias i én versjon. Oppdater `backend/api_models.py`, `frontend/lib/contracts.ts` og `frontend/lib/model/plan.ts`.
  - «Squad Outlook»-totalen skal være summen av de viste cellene.
- **Tester:** en kontrakttest som sjekker at feltene er like. En frontend-test som sjekker at viste celler summerer til totalen.

### M4. Horisonten bruker ikke denne ukas tilgjengelighet eller blank på alle GW (ISSUE-005)

- **Problem:** `backend/planning_service.build_fixture_scaled_horizon` skalerer `predicted_points` (= `ml_prediction × availability_multiplier`) til GW2–5. En spiller med 0 % sjanse eller suspensjon denne uka, eller som blanker i base-GW, får 0 i alle fem.
- **Endring:**
  - Skaler fremtidige GW-er fra `ml_prediction`, altså verdien hvis spilleren er tilgjengelig. Kolonnen finnes i v12+-artefakter. Faller tilbake til dagens oppførsel for legacy.
  - Bruk full multiplikator bare på GW1.
  - Bruk en avtagende versjon på GW2 for statusene `d` og `i` med sjanse > 0. Behandle status `i` med sjanse `None` som ukjent varighet og gi en navngitt, dokumentert regel.
  - Blank i base-GW: bruk `ml_prediction` og per-fixture-faktor.
- **Tester:** 0 % i GW1 gir > 0 i GW3–5. Blank i GW1 gir > 0 i GW2.

### M5. Konfidens, aksjonslabel og wildcard-signal (ISSUE-006)

- **Problem:**
  - `transfer_pressure` trekker 1 GW fra 5 GW, så aksjonen blir alltid `MULTI_TRANSFER`.
  - `confidence` mettes og er alltid `HIGH`.
  - `_wildcard_pressure` måles mot `optimize_squad(budget=100)` og er alltid 1,0, så WC anbefales når den er tilgjengelig.
- **Endring:**
  - Fjern `transfer_pressure` fra aksjonsvalget. Aksjonen følger av M2.
  - Confidence = margin mellom valgt plan og beste alternativ (inkludert rull), delt på en usikkerhetsskala. Bruk for eksempel `sqrt(Σ uncertainty²)` for de berørte spillerne. Terskler skal være navngitte konstanter med kommentar.
  - Wildcard: anbefal bare når `best_wildcard_squad_horizon_value − best_transfer_plan_value > WC_THRESHOLD`. WC-laget beregnes med MILP over ekte budsjett (bank pluss salgsverdier) og samme XI-bevisste objektiv som M1.
  - Fjern `optimal_squad`-beregningen fra request-pathen hvis den ikke trengs til dette.
- **Tester:** liten margin gir `LOW` eller `MEDIUM`. Et sunt lag gir ikke WC-anbefaling. Én transfer gir `TRANSFER`, ikke `MULTI_TRANSFER`.

### M6. Feil Team ID og upstream-feil (ISSUE-007, ISSUE-012)

- **Problem:** Ukjent ID gir ufanget `TeamServiceError`, som blir en ren-tekst-500 uten CORS. Frontend viser «Failed to fetch». Gatewayen forsøker 404 på nytt. Dashboardet svelger årsaken («decision, planning_state»).
- **Endring:**
  - `backend/fpl_gateway.py`: `FplNotFoundError` for 404, uten retry og uten cache av feilen.
  - `get_dashboard_v1` og øvrige team-ruter: 404 JSON ved ukjent lag («Fant ikke et FPL-lag med ID …»), 502 JSON ved upstream-feil.
  - En global exception handler som alltid gir JSON.
  - `dashboard_service.build_dashboard`: legg en maskinlesbar `code` per feilområde (`FORECAST_NOT_PUBLISHED`, `FPL_UNAVAILABLE`, `TEAM_NOT_FOUND`, `INTERNAL`) og en eventuell `retry_after`. Ta vare på meldingen fra `HTTPException.detail`.
  - Frontend (`ConnectHero.tsx`, `DataState.tsx`, `PlanWorkspace.tsx`, `AppShell`-banner): mapp koder til menneskelig tekst. Fjern «Try refreshing» når refresh ikke kan hjelpe.
- **Tester:** backend-tester for 404, 502 og CORS-header på feilrespons. Frontend-tester for «Team not found» og for tom-tilstanden når prognosen ikke er publisert.

### M7. Hits og sannferdig UI-tekst (ISSUE-008, ISSUE-009)

- **Endring:**
  - `backend/main.py:934-938`: søk opp til `FT + 2` transfers, uavhengig av FT. Hit-terskelen i `decision_strategy` skal gjelde netto **XI**-gevinst over horisonten, etter M1–M3.
  - Rett `decision_intelligence._insights`, som leser `net_gain` mens nøkkelen er `current_net_gain`.
  - Fjern eller erstatt tekster som ikke stemmer med logikken: «clears its threshold after cost and uncertainty», «only proposes a hit when …» og generiske «Why this plan»-setninger.
  - Generer konkrete begrunnelser fra tallene i den valgte planen: ut- og inn-spillerens xP per GW og motstander, hit, rulleverdi og margin.
- **Tester:** FT=0 med bare en benkoppgradering gir `HOLD`. Insight-evidensen inneholder faktisk netto gevinst.

### M8. Planlegging rett etter fristen (ISSUE-001)

- **Problem:** `predict_gw.main()` publiserer N+1 først når N er ferdig og datasjekket. `_validate_prediction_target` avviser N-prognosen når N+1 er target. Planleggingen er låst 3–5 dager i uka. Det var tilfellet under auditen: GW6 live og ingen GW7-plan.
- **Endring:**
  - Publiser en `provisional` N+1-prognose når N-fristen har passert. Bruk historikk til og med N−1 og samme `forecast.py`-path. Manifestet får `"stage": "provisional" | "final"`.
  - Den endelige prognosen erstatter den foreløpige når N er datasjekket. Behold dagens sertifiserings- og paritetssjekker for begge.
  - `_validate_prediction_target` godtar begge. `meta` eksponerer `stage`.
  - Frontend viser «Foreløpig plan – oppdateres når GW N er ferdig».
  - Oppdater `.github/workflows/refresh-predictions.yml` om nødvendig.
- **Tester:** pipeline-test for provisional, deretter final. API-test som viser at dashboardet gir en plan med `stage=provisional` mellom fristen og datasjekken.

---

## SHOULD FIX (etter MUST)

- **S1. Salgspriser (ISSUE-011):**
  - Utled kjøpspris fra `entry/{id}/transfers/` (`element_in_cost`, siste kjøp).
  - For spillere fra startlaget: bruk `element-summary/{id}` sin pris i `started_event`.
  - Bruk FPL-regelen (halvparten av fortjenesten, rundet ned til 0,1).
  - Merk kilden `derived_purchase_price`.
  - Test kjøp, prisøkning og prisfall.
- **S2. Captain (ISSUE-010):**
  - Ikke multipliser tilgjengelighet og start på nytt i `_captain_score`.
  - Legg til en eksplisitt ceiling-komponent og vis margin til nummer 2.
  - Visekaptein bør foretrekke en annen kamp eller klubb når scoren er nesten lik.
- **S3. Skalering (ISSUE-013):**
  - Poll bare live-data mens GW er live.
  - Cache beslutningen per (lag, prognoseversjon, FT-override, bootstrap-tidsstempel).
  - Vektoriser `_apply_official_player_state` og kjør den én gang per request.
- **S4. Verifiser FT-regelen etter Wildcard/Free Hit (`live_service.derive_free_transfers`)** mot offisiell regeltekst, og legg kilden i en kommentar og en test.
- **S5. Små UI-feil:**
  - Rank-aksen skal ikke vise negative verdier (`TrendChart.tsx:46`).
  - Merknad om at transfers gjort etter fristen ikke er synlige (ISSUE-015).
  - Last markedsdata for alle innkommende spillere i planen, ikke bare de 50 beste, slik at «Next GW» ikke blir «—».

## NICE TO HAVE

- Prognose per GW i horisonten med lagstyrke (`strength_*` i bootstrap) og xG/xA i stedet for ±8 %-FDR-skalering. Krever ny sertifisering. Sertifiseringen skal også rapportere Spearman, siden modellen i dag rangerer dårligere enn baseline: 0,618 mot 0,667.
- Chip-planlegging over flere GW (BB/TC på kommende DGW-er, WC-timing).
- Skade-, nyhets- og prisvarsler.
- Rydding (merk deprecated først, slett etter grep-verifikasjon):
  - `models/prediction_engine.py`, `fpl.py`, legacy-Streamlit (`app.py`, `app_team.py`, `fpl.db`) og tilhørende tester;
  - ubrukte backend-ruter (`/players/top` med «team 1»-hacken, `/api/v1/plan` som ignorerer FT-override, `/live/players`, `/fixtures/team/*`);
  - døde risikolabels i `decision_risk.py`;
  - utdaterte dokumenter (`ARCHITECTURE.md`-AI-laget, `PROJECT_HANDOFF.md` «no scheduler», v3-kommentaren i `requirements-pipeline.txt`).

## Leveranse

1. Én PR per fase (M1–M3, M4–M5, M6–M7, M8, så SHOULD). Hver PR skal ha før/etter-tabellen fra runtime-re-testen.
2. Oppdater README og docs der oppførselen endres (horisont, hits, foreløpig prognose).
3. Rapporter eksplisitt hva som er VERIFIED i runtime, hva som bare er testet i enhetstester, og hva som ikke kunne testes.
