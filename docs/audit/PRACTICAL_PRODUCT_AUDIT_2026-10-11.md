# FOOTBALL FANTASY AI — PRACTICAL PRODUCT AUDIT

Dato: 2026-10-11 · Kodebase: `master` @ `5306fdc` · Sesong 2026-27, GW6 live, neste frist GW7 (17.10).

## Metode

- Kjørte hele stacken lokalt: FastAPI-backend (`uvicorn backend.main:app`) mot det **ekte** FPL-API-et, og Next.js-frontend (`pnpm build && pnpm start`).
- Testet UI-et i Chromium (Playwright) på desktop (1440 px) og mobil (390 px), for alle sider.
- Akkurat nå er GW6 live, og den publiserte prognosen gjelder GW6. Planleggingen er derfor låst (se ISSUE-001). For å teste beslutningsmotoren kjørte jeg også en **simulert backend**: den eneste endringen var at bootstrap-flaggene ble satt til «rett før GW6-fristen». Alt annet var ekte FPL-data og ekte GW6-lagvalg.
- Kjørte motoren på **12 ekte lag**: topp 3 i Overall, et lag rundt rank 20 000, de to første Team ID-ene, demo-laget 6658075 og fem andre. Testet også FT-override 0/2/3.
- Statusene i rapporten betyr:
  - **VERIFIED**: observert i runtime.
  - **CODE**: bekreftet ved å lese koden og/eller med et lite skript.
  - **NOT VERIFIED**, **BLOCKED** og **BROKEN** brukes som i oppdraget.

### Kjøring og sjekker

| Sjekk | Status |
|---|---|
| `python -m pytest tests backend/tests` | VERIFIED: 476 passed, 1 skipped |
| `pnpm test` | VERIFIED: 24 filer, 106 tester passed |
| `pnpm lint` / `pnpm exec tsc --noEmit` | VERIFIED: rene |
| `pnpm build` | VERIFIED |
| Backend lokalt mot ekte FPL | VERIFIED |
| `docker compose build` | BLOCKED (Docker finnes ikke i miljøet) |
| Hostet app (Vercel/Railway) | NOT VERIFIED. Forsiden svarer 200, men brukerreisen ble ikke testet der. |
| Prognose-pipeline (`refresh_predictions`) | NOT VERIFIED. Ikke kjørt, fordi GW6 ikke er ferdig. |

---

## 1. Executive Summary

Football Fantasy AI ser ut og føles som et ferdig produkt. Frontend er gjennomarbeidet: tydelig førstegangsopplevelse, god Team ID-forklaring, live-cockpit, pitch-editor med lovlige formasjoner, kildemerking (Official/Model/Derived) og ærlige forbehold. Data-pipelinen har uvanlig god disiplin rundt lekkasje, manifest og produksjonsparitet.

**Selve FPL-rådene holder derimot ikke.** I alle 12 testede lag var resultatet det samme:

- motoren anbefalte transfer, aldri HOLD eller rull;
- confidence var «HIGH» (0,88–0,99);
- `wildcard_pressure` var 1,0;
- aksjonen het «MULTI_TRANSFER», også når forslaget var én transfer.

I 7 av 12 lag brukte motoren en transfer på en reservekeeper, fordi transferoptimereren maksimerer poeng for alle 15 spillere, ikke for XI-en. I 4 av 12 lag inneholdt samme API-svar to forskjellige anbefalte transfers. En skadet spiller med 0 % sjanse denne uka får 0 poeng i alle fem GW-er i horisonten, og blir dermed solgt.

I tillegg er planleggingen **helt utilgjengelig hver uke**, fra fristen til forrige GW er ferdig og datasjekket. I dag er det tilfellet: «No plan available» for GW7 fem dager før fristen.

En erfaren FPL-manager ville raskt sluttet å stole på rådene. Produktet er en flott **teknisk prototype med produktskall**. Beslutningslaget må rettes før det er et pålitelig ukentlig verktøy.

| Område | Score | Kort begrunnelse |
|---|---|---|
| Product readiness | **5/10** | Polert UI. Men planleggingen er låst 3–5 dager i uka, og rådene er systematisk skjeve. |
| FPL decision quality | **3/10** | Aldri hold/rull, benk-keeper-transfers, dobbelttelling, skadet = 0 over 5 GW, konstant HIGH-confidence. |
| Data reliability | **6/10** | Offisielle data og manifest-validering er solide. Salgspris er estimert, og FT-regelen er uverifisert. |
| UX | **7/10** | Svært god flyt og visuelt språk. Svak feilhåndtering (ukjent ID, låst plan) og påstander i teksten som ikke stemmer. |
| Architecture | **5/10** | God separasjon backend/frontend/pipeline. To konkurrerende transfer-rangeringer, mange ubrukte ruter og legacy-moduler. |
| Test coverage | **5/10** | Mange tester (582), men ingen fanger produktinvariantene som feiler (benk-verdi, hold, konsistens). |
| Reliability | **5/10** | Feiler kontrollert ved stale data. Ukjent Team ID gir 500 uten CORS, og global kvote på 60 forespørsler/min mot FPL. |

---

## 2. What Works Very Well (verifisert)

1. **Førstegangsopplevelsen** (VERIFIED, desktop og mobil):
   - Tydelig verdiforslag.
   - Team ID-feltet godtar både ID og hel FPL-URL (`entry/(\d+)`).
   - Hjelpetekst viser hvor ID-en finnes.
   - «Try gawi's team» lar deg se produktet uten egen ID.
   - Lenker til Players og Fixtures uten ID.
   - Ingen horisontal scroll på 390 px.
2. **Lokal validering av Team ID** (VERIFIED): «abc12» gir en presis feilmelding uten nettverkskall.
3. **Persistens** (VERIFIED): Team ID ligger i `localStorage`, så refresh og navigering beholder laget. FT-override lagres per lag og GW (`lib/freeTransfers.ts`).
4. **Live-cockpit** (VERIFIED i dag med GW6 live):
   - live-poeng, captain-bidrag, spilt/spiller/gjenstår;
   - modellens forventning (46,8 xP) mot faktisk (58);
   - benk vises som «not counted unless auto-subbed»;
   - korrekt kaptein (Palmer ×2).
5. **Ærlig degradering** (VERIFIED):
   - Når prognosen ikke matcher neste GW, avviser backenden å lage en plan (503 og `actions_locked`), i stedet for å vise råd for feil GW.
   - My Team viser «The deadline has passed, so this is a what-if view only».
6. **Kildemerking og forbehold** (VERIFIED):
   - «1 free transfer, estimated from your public transfer history — Not right? Set yours».
   - «Affordability is estimated from market prices».
   - «Model / Official / Derived»-merker overalt.
7. **Pitch-editor** (CODE og VERIFIED): `lib/fpl/rules.ts` `validateStartingXI` og `optimizer/starting_xi.py` gir alltid lovlig formasjon. Alle 12 lag fikk lovlige formasjoner (3-4-3, 3-5-2, 4-4-2, 5-3-2).
8. **MILP-transferoptimereren håndhever hard-reglene** (VERIFIED på 12 lag og FT 0–3):
   - budsjett (bank pluss salg);
   - posisjonsfordeling 2/5/5/3;
   - maks 3 per klubb.
   - Ingen anbefaling brøt reglene.
9. **Disiplin i prognose-pipelinen** (CODE): én felles feature-implementasjon (`historical_data/forecast.py`), manifest med SHA-sjekker, kontroll av target-GW og sesong, kausalitets- og paritetssertifikat, og skjema-validering ved oppstart.
10. **Chip-tilstand** (VERIFIED): brukte chips per halvdel leses korrekt fra historikken, for eksempel at topplaget har brukt alle fire i første halvdel.
11. **Ytelse**: dashboard tar 1,1 s med varm cache og ca. 4 s kaldt, inkludert 6 MILP-løsninger.

---

## 3. Critical Issues

### ISSUE-001: Planleggingen er låst fra fristen til forrige GW er ferdig

- **Severity:** CRITICAL
- **Area:** Pipeline og produktflyt
- **Observed behavior (VERIFIED i dag):**
  - `/api/v1/status` gir `service_state: degraded` med feilen «Prediction GW6 does not match official target GW7».
  - Plan & Transfers viser «No plan available — The decision engine returned no plan … Try refreshing».
  - Banneret sier «Some analysis is unavailable (decision, planning_state)».
  - Dette skjer 5 dager og 20 timer før GW7-fristen.
- **Expected behavior:** Brukeren skal kunne planlegge GW N+1 så snart GW N-fristen har passert. Det er da de fleste gjør research.
- **How reproduced:** Start backend i dag. Kall `GET /api/v1/dashboard/9100001` (`decision: null`) og `GET /api/decision/9100001` (503).
- **Probable root cause:** `historical_data/current_data/predict_gw.py` kaster `HistoryIncompleteError` til alle tidligere GW-er er `finished` og `data_checked`. Samtidig avviser `backend/main.py:_validate_prediction_target` den forrige GW-ens prognose. Resultatet er et hull hver uke. `forecast_checks.csv` har bare GW3 (legacy). Det finnes ingen artefakter for GW4 og GW5, så produktet hadde trolig ingen prognose de ukene heller (NOT VERIFIED historisk).
- **Relevant files:** `historical_data/refresh_predictions.py`, `historical_data/current_data/predict_gw.py`, `backend/main.py:104` (`_validate_prediction_target`), `.github/workflows/refresh-predictions.yml`, `frontend/components/plan/PlanWorkspace.tsx`.
- **Recommended fix:**
  1. Publiser en **foreløpig prognose for N+1** så snart fristen for N har passert. Bruk historikk til og med N−1 og merk den `provisional`. Erstatt den med den endelige når N er datasjekket.
  2. La valideringen godta `provisional` for target-GW.
  3. Vis «Foreløpig – oppdateres når GW N er ferdig» i UI.
  4. Gi plan-siden en spesifikk tom-tilstand («GW7-prognosen publiseres <tid>»), i stedet for «Try refreshing».

### ISSUE-002: Transferoptimereren verdsetter benk og reservekeeper som startspillere

- **Severity:** CRITICAL
- **Area:** Transfer engine
- **Observed behavior (VERIFIED, simulert pre-deadline GW6):**

  | Lag | Anbefaling | Problem |
  |---|---|---|
  | 9100011 | Forster (benk-GK, 0 xMins) → Pickford, «+12,5» som eneste transfer | Pickford blir benket, fordi laget allerede har en spillende keeper. |
  | 9100006, 9100007, 9100009, 9100010, 9100004, 9100005 | Alle bruker én av transferene på reservekeeperen | Samme feil. |
  | 9100001, FT=3 | `Forster→Tzolakis`, `Slater (benk)→Rashford` | Benkeplasser oppgraderes. |

- **Expected behavior:** Gevinsten skal måles på forventet **XI-poengsum**, inkludert sannsynlig innbytte, ikke som summen av alle 15. En benk-GK-oppgradering har nesten null verdi.
- **Probable root cause:** `transfer_analysis.py:optimize_transfer_plan`. Objektivet `-points` summeres over alle 15 valgte spillere (`objective = np.r_[-points * ...]`), og `gain = in.predicted_points - out.predicted_points` per bytte.
- **Relevant files:** `transfer_analysis.py:616-863`, `optimizer/transfer_optimizer.py`, `optimizer/starting_xi.py`.
- **Recommended fix:**
  - Utvid MILP-en med startvariabler `s_i ≤ x_i`: 11 startere, gyldig formasjon (1 GK, 3–5 DEF, 2–5 MID, 1–3 FWD).
  - Objektiv: `Σ s_i·pts_i + Σ (x_i − s_i)·pts_i·w_bench`, der `w_bench` er ca. 0,1–0,15 for utespillere og ca. 0,02 for benk-GK.
  - Gjør dette per GW i horisonten, eller med vektet aggregat.
  - Legg til regresjonstest: «aldri anbefal benk-GK-bytte når GK1 er tilgjengelig».

### ISSUE-003: Motoren anbefaler aldri HOLD eller rull, og bruker alltid alle FT

- **Severity:** CRITICAL
- **Area:** Transfer engine og strategi
- **Observed behavior (VERIFIED):**
  - 12 av 12 lag fikk transfer, også topp 1 i Overall, som et sterkt lag uten åpenbare problemer (scenario A).
  - Med FT=2 eller 3 brukte motoren alle (scenario E).
  - HOLD kom bare med FT=0, der hit-regelen slo inn.
- **Expected behavior:**
  - En liten gevinst skal veies mot verdien av å rulle en FT (ca. 1–2 poeng over horisonten, avhengig av antall banket).
  - Motoren bør vurdere å bruke 0, 1, 2 … n transfers og vise «Roll» som et reelt alternativ med sammenlignbar score.
- **Probable root cause:**
  - `transfer_analysis.py` sorterer planer på `net`. Rull-planen har `net=0`, så enhver positiv gevinst vinner.
  - `decision_strategy.choose_transfer_action` gir HOLD bare når `net_gain <= 0`.
  - Det finnes ingen modell for FT-verdi. `max_transfers = min(5, max(1, FT))` (`backend/main.py:934`).
- **Relevant files:** `transfer_analysis.py`, `decision_strategy.py:6-21`, `backend/main.py:929-938`.
- **Recommended fix:**
  - Innfør `roll_value(ft_banked)` som konfigurerbar konstant, validert med backtest (`backtesting/decision_backtest.py`).
  - En transfer anbefales bare når `net_horizon_gain > roll_value + margin`.
  - Returner eksplisitt `ROLL` med begrunnelse («Best move +0,8 over 5 GW < verdien av å rulle»).

### ISSUE-004: To forskjellige transferanbefalinger i samme svar, og horisonten telles to ganger

- **Severity:** HIGH
- **Area:** Konsistens og beslutningslag
- **Observed behavior (VERIFIED):**
  - Lag 9100001: `transfers.recommended` er Szoboszlai→Rashford (net 6,21). `intelligence.transfer_strategy.selected_transfers` er Schade→Groß. UI viser Schade→Groß.
  - Samme avvik i 6658075, 9100008 (alle tre transfers forskjellige) og 5416316.
  - Frontend viser «5-GW gain» fra intelligence-laget, mens selve optimereren rangerte på noe annet.
- **Probable root cause:**
  - `optimizer/transfer_optimizer.py` bytter allerede `predicted_points` ut med en **vektet 5-GW-score** (`aggregate_multi_gw_value`, vektene 1/0,85/0,7/0,55/0,4). `net_gain` er altså allerede en horisontverdi.
  - `decision_intelligence._select_horizon_transfer` legger så til `horizon_gain`, som er en ny 5-GW-sum, minutt-justert med `0,5 + 0,5·xmins/90`.
  - Rangeringen skjer på `combined_score = net_gain + horizon_gain`. Det er dobbelttelling med to forskjellige vektinger, og kan velge en annen plan enn optimereren.
  - Feltet `current_net_gain` er feilmerket: det er ikke «current GW».
- **Relevant files:** `decision_intelligence.py:79-152`, `optimizer/transfer_optimizer.py:27-49`, `decision_engine.py:64-89`, `frontend/lib/model/plan.ts:201-210`.
- **Recommended fix:**
  - Én rangering, ett tall. Optimereren eier valget.
  - Intelligence-laget skal bare forklare og beregne visningsmetrikker for den valgte planen (neste GW, 5 GW, hit).
  - Fjern `combined_score` som rangering, eller la den være identisk med optimererens objektiv.
  - Gi feltene entydige navn (`next_gw_gain`, `horizon_gain_weighted`, `hit_cost`, `net_horizon_gain`).

### ISSUE-005: Denne ukas tilgjengelighet og blank smitter over på hele 5-GW-horisonten

- **Severity:** HIGH
- **Area:** Horisont, skade og suspensjon (scenario B og C)
- **Observed behavior (CODE og skript-verifisert):** Saka med 0 % sjanse denne uka får 0,0 poeng i GW6–GW10. Uten flagg får han 4,9 / 4,62 / 4,9 / 4,24 / 5,28. Det samme gjelder en suspensjon på én kamp og en spiller hvis lag blanker i base-GW.
- **Expected behavior:**
  - Tilgjengelighet skal gjelde de GW-ene den faktisk påvirker.
  - Statusene `d` og `i` med nyheter bør gi en gradvis retur.
  - Suspensjon bør gjelde bare antall kamper i utestengelsen.
  - Blank i base-GW skal ikke nulle fremtidige GW-er.
- **Probable root cause:** `backend/planning_service.build_fixture_scaled_horizon` skalerer `predicted_points` fra base-GW, som allerede er multiplisert med tilgjengelighet i `backend/main._apply_official_player_state`, til alle fremtidige GW-er.
- **Relevant files:** `backend/planning_service.py:62-171`, `backend/main.py:132-182`.
- **Recommended fix:**
  - Skaler fremtidige GW-er fra `ml_prediction` (verdien hvis spilleren er tilgjengelig).
  - Bruk tilgjengelighets-multiplikatoren bare på GW1, og en avtagende versjon på GW2 for statusene `d` og `i`.
  - Blank i base-GW: skaler fra `ml_prediction` og per-fixture-faktor, ikke fra 0.

### ISSUE-006: Confidence, aksjon og wildcard-signal er alltid «maks»

- **Severity:** HIGH
- **Area:** Beslutningsforklaring og chips (scenario G)
- **Observed behavior (VERIFIED, 12 av 12 lag):**
  - `action = MULTI_TRANSFER`, også med én transfer.
  - `confidence.label = HIGH` (0,88–0,99).
  - `wildcard_pressure = 1.0`.
  - Wildcard ble anbefalt for 9100002 (topp 2) og 9100008, kun fordi WC var tilgjengelig.
- **Probable root cause:**
  - **Aksjon:** `decision_strategy.transfer_pressure` sammenligner en 5-GW-sum med én GW (`future − current) / 8`. Det blir nesten alltid ≥ 0,65 og gir dermed «MULTI_TRANSFER».
  - **Confidence:** `decision_margin = |net| / 6`, der `net` er en 5-GW-verdi og derfor mettes raskt. `fixture_certainty` er dekningsgrad (alltid 1). `signal_agreement` er alltid 1 når net > 0.
  - **Wildcard:** `decision_intelligence._wildcard_pressure` er overlapp mot `optimize_squad(budget=100)` for én GW. Nesten ingen spillere overlapper med et teoretisk optimum, så `turnover·1,5` mettes. `chip_advisor` anbefaler WC ved `wildcard_pressure ≥ 0,75`.
- **Relevant files:** `decision_strategy.py`, `decision_intelligence.py:154-167, 252-300`, `decision_engine.py:62`.
- **Recommended fix:**
  - **Aksjon** = `HOLD | ROLL | TRANSFER | MULTI_TRANSFER`, avledet fra antall valgte transfers.
  - **Confidence** = margin mellom beste plan og nest beste (eller rull) relativt til usikkerheten (sum av `uncertainty`), kalibrert med backtest.
  - **Wildcard:**
    - mål forventet 5-GW-gevinst av beste WC-lag (MILP med ekte budsjett og salgspriser) mot beste 1–2-transfer-plan;
    - anbefal WC bare når differansen er stor over flere GW-er;
    - fjern `optimize_squad(budget=100)` fra request-pathen hvis den ikke brukes til dette.

### ISSUE-007: Ukjent Team ID gir 500 uten CORS, og UI viser «Failed to fetch»

- **Severity:** HIGH
- **Area:** Team ID-import og robusthet
- **Observed behavior (VERIFIED):**
  - `GET /api/v1/dashboard/999999999` gir `500 Internal Server Error` som ren tekst.
  - I nettleseren vises «Failed to fetch» under Team ID-feltet.
  - Upstream-404 ble i tillegg forsøkt på nytt (to kall).
- **Expected behavior:** 404 «Fant ikke et FPL-lag med ID 999999999. Sjekk tallet i URL-en din.» Ingen ny forsøk ved 4xx.
- **Probable root cause:**
  - `get_dashboard_v1` fanger ikke `TeamServiceError` fra `dependencies.team`, som kalles utenfor try i `dashboard_service.build_dashboard`.
  - Ufangede unntak gir en Starlette-500 uten CORS-headere.
  - `fpl_gateway.get_json` skiller ikke 404 fra 5xx.
- **Relevant files:** `backend/main.py:992-1059`, `backend/dashboard_service.py:41`, `backend/fpl_gateway.py:120-152`, `backend/team_service.py:24-30`.
- **Recommended fix:**
  - Typet `FplNotFoundError` i gatewayen, uten retry og uten caching av feilen.
  - Map til `HTTPException(404)` i dashboardet.
  - Map øvrige upstream-feil til 502 med JSON.
  - Global exception handler som alltid returnerer JSON (CORS-middlewaren legger da på headere).

### ISSUE-008: Hits vurderes aldri som standard, men UI sier at de gjør det

- **Severity:** MEDIUM
- **Area:** Transfer engine og UX-sannferdighet
- **Observed behavior (VERIFIED):**
  - `max_transfers = max(1, FT)`, så antall transfers kan aldri overstige FT, og hit vurderes aldri, unntatt når FT=0.
  - Plan-siden sier likevel «The engine only proposes a hit when the multi-GW edge clearly exceeds it».
  - Med FT=0 viste demo-laget 6658075 en −4-hit på Konsa (benkspiller) → Gabriel.
- **Probable root cause:** `backend/main.py:934-938`, terskelen i `decision_strategy.py:13`, og ISSUE-002 (benk telles).
- **Recommended fix:**
  - Søk alltid opp til `FT + 2` transfers.
  - En hit godtas bare når netto XI-gevinst over horisonten overstiger hit pluss margin.
  - Vis «−4 hit» eksplisitt med begrunnelse.

### ISSUE-009: Forklaringer som ikke stemmer med logikken

- **Severity:** MEDIUM
- **Area:** AI-forklaring
- **Observed behavior (VERIFIED):**
  - `intelligence.insights[TRANSFER].evidence.net_gain` er alltid `0.0`, fordi `_insights` leser `transfer.get("net_gain")` mens blokken bruker nøkkelen `current_net_gain`.
  - Plan-headeren sier «The engine found a move that clears its threshold after cost and uncertainty». Det finnes ingen terskel og ingen usikkerhetsvurdering.
  - «Why this plan»-teksten er generisk og lik for alle lag.
- **Relevant files:** `decision_intelligence.py:169-226`, `frontend/components/plan/PlanWorkspace.tsx`, `frontend/components/plan/WhySheet.tsx`.
- **Recommended fix:**
  - Rett nøkkelen.
  - Generer konkrete, tallbaserte begrunnelser fra den valgte planen: fixture-run for ut- og inn-spiller per GW, minutter, pris.
  - Fjern påstander koden ikke gjør.

### ISSUE-010: Captain-logikken er enkel og straffer minutter dobbelt

- **Severity:** MEDIUM
- **Area:** Captain
- **Observed behavior (VERIFIED):**
  - Haaland var captain i 11 av 12 lag. Det er rimelig.
  - Forsvarere dukker opp som captain-alternativer: Gabriel på 3. plass (lag 9100001), Tarkowski som visekaptein (lag 9100009).
  - Modellens toppverdi er bare 5,5 xP, så alt er komprimert.
- **Probable root cause:**
  - `decision_intelligence._captain_score` = `pp × (0,55 + 0,45·start) × availability_factor × fixture_factor`.
  - `pp` er allerede multiplisert med tilgjengelighet og påvirket av FDR, så minutter, tilgjengelighet og fixture telles to–tre ganger.
  - Ingen ceiling eller haul-sannsynlighet, ingen straffe eller dødball, ingen xG eller xA.
  - Captain velges per GW uten blikk på dobbeltrunder.
- **Relevant files:** `decision_intelligence.py:19-30`, `decision_engine.py:100-108`.
- **Recommended fix:**
  - Kapteinsscore = forventet ekstra poeng (= `pp`) pluss en eksplisitt ceiling-komponent, for eksempel P(≥ 10 poeng) fra en enkel fordeling (Poisson på mål og assist) eller historisk varians per posisjon.
  - Ikke multipliser tilgjengelighet på nytt.
  - Vis «captain floor/ceiling» og margin til nummer 2.

### ISSUE-011: Salgspriser estimeres som markedspris, men kan utledes fra offentlige data

- **Severity:** MEDIUM
- **Area:** Budsjett (scenario D)
- **Observed behavior (VERIFIED):** Alle lag har `selling_price_source: market_price_estimate` og `budget_is_estimate: true`. For en spiller som har steget i pris, overvurderes budsjettet, og forslaget kan være umulig i FPL.
- **Probable root cause:** Picks-endepunktet er offentlig uten `selling_price`. `transfer_analysis.selling_value` bruker kjøpspris bare hvis den er oppgitt.
- **Recommended fix:**
  - Utled kjøpspris fra `entry/{id}/transfers/` (`element_in_cost` for siste kjøp av spilleren).
  - For spillere fra startlaget: bruk `element-summary/{id}` sin `value` i `started_event`.
  - Wildcard og Free Hit tilbakestiller ikke kjøpspris. Free Hit-lag reverseres.
  - Merk kilden `derived_purchase_price`.

### ISSUE-012: Feilmeldinger i dashboardet mister årsaken

- **Severity:** MEDIUM
- **Area:** UX og backend
- **Observed behavior (VERIFIED):**
  - Banneret viser intern sjargong: «Some analysis is unavailable (decision, planning_state)».
  - Plan-siden sier «Try refreshing», selv om refresh aldri hjelper (ISSUE-001).
- **Probable root cause:** `dashboard_service.build_dashboard` svelger unntaket (`except Exception`) og gir en generisk melding. `get_decision`s `HTTPException(503, "Prediction GW6 does not match …")` forsvinner.
- **Recommended fix:**
  - Ta med en maskinlesbar `code` per område (`FORECAST_NOT_PUBLISHED`, `FPL_UNAVAILABLE`, `TEAM_NOT_FOUND`) og `retry_after`.
  - Frontend mapper koden til en menneskelig tekst.

### ISSUE-013: Skalering mot FPL-API-et

- **Severity:** MEDIUM
- **Area:** Robusthet
- **Observed behavior (CODE):**
  - Global grense på 60 upstream-kall per minutt (`fpl_gateway.MAX_UPSTREAM_REQUESTS_PER_MINUTE`).
  - Hvert nytt lag krever ca. 4 unike kall (entry, picks, history, transfers).
  - Frontend poller hele dashboardet hvert 60. sekund per åpen fane (`TeamProvider.REFRESH_INTERVAL_MS`), inkludert 6 MILP-løsninger.
  - Ved ca. 15 nye lag i minuttet går kvoten tom, og dashboardet feiler for alle brukere uten cache.
- **Recommended fix:**
  - Poll bare live-data (`/team/{id}/live`) når GW er live.
  - Ikke kjør beslutningen på nytt før input endres (cache per lag, prognoseversjon og FT-override).
  - Øk TTL for entry, history og transfers før fristen.
  - Skill 4xx fra 5xx i gatewayen.

### ISSUE-014: Rank-grafen viser negative rank-verdier

- **Severity:** LOW
- **Area:** UI
- **Observed behavior (VERIFIED):** Y-aksen i Season-kortet viser «-218» for lag 9100001 (rank 1).
- **Root cause:** `frontend/components/charts/TrendChart.tsx:46` trekker fra `span·0,08` uten nedre grense.
- **Fix:** Klem til ≥ 1 for rank.

### ISSUE-015: Transfers gjort før fristen er usynlige

- **Severity:** LOW
- **Area:** Team ID og produktforventning
- **Observed behavior (CODE og FPL-API):** Før fristen returnerer det offentlige API-et forrige GWs picks og ikke ukens ventende transfers. En manager som allerede har gjort bytter, får råd for sitt gamle lag.
- **Fix:** Vis en tydelig merknad («Bytter du har gjort etter GW N-fristen vises ikke før neste frist»). Vurder å la brukeren markere spillere som solgt eller kjøpt manuelt.

---

## 4. Incorrect or Suspicious FPL Logic

| # | Funn | Type |
|---|---|---|
| L1 | Transfer-objektivet summerer alle 15 spillere (ISSUE-002) | **Bug** |
| L2 | Ingen rulleverdi, så aldri HOLD (ISSUE-003) | **Bug / manglende modell** |
| L3 | Horisonten dobbelttelles: vektet 5-GW `net_gain` pluss minutt-justert 5-GW `horizon_gain` (ISSUE-004) | **Bug** |
| L4 | Tilgjengelighet og blank fra base-GW kopieres til alle 5 GW (ISSUE-005) | **Bug** |
| L5 | `transfer_pressure`: enhetsfeil (5 GW minus 1 GW) (ISSUE-006) | **Bug** |
| L6 | `wildcard_pressure` mot et optimum med 100 m budsjett og én GW (ISSUE-006) | **Tvilsom antakelse** |
| L7 | Minutter straffes 2–3 ganger: modell-`pp` × tilgjengelighet, deretter `0,5+0,5·xmins/90` i horisonten og `start`/`availability_factor` i captain | **Bug / svak modell** |
| L8 | `decision_risk` har straffer for statusene `NEWS`, `MINOR_RISK`, `MAJOR_RISK` og rotasjon, som backenden aldri produserer. Den produserer bare `AVAILABLE`, `RISK` og `UNAVAILABLE`, og `rotation_risk` er alltid tom. | **Død logikk** |
| L9 | Fremtidige GW-er skaleres fra neste GW-prognose med ±8 % per FDR-steg (`_fixture_factor`). Saka varierer bare 4,24–5,28 over fem kamper. Fixture-swing slår nesten ikke ut. | **Svak modell** (README nevner det) |
| L10 | FDR er eneste mål på motstanderstyrke. Det finnes ingen angreps- eller forsvarsstyrke, selv om FPL-bootstrap har `strength_attack_home` osv. | **Svak modell** |
| L11 | Chip-råd for Bench Boost og Triple Captain er rene regler: DGW-flagg gir BB 0,80, og DGW pluss `net_gain > 3` gir TC. Det siste kobler TC til *transfergevinst*, som er meningsløst. | **Tvilsom antakelse** |
| L12 | FT etter Wildcard/Free Hit: koden gir uka etter chip samme antall FT som chip-uka (`live_service.derive_free_transfers`). Det må verifiseres mot offisiell regeltekst. | **Krever verifikasjon** |
| L13 | `optimize_squad(budget=100)` («optimal squad») bruker 100 m, ikke lagets faktiske verdi, og brukes bare til L6 | **Produktvalg / unødvendig** |
| L14 | Hit-terskel `max(0,75, hit·0,75)` = 3 poeng sammenlignet med en *vektet 5-GW*-gevinst inkludert benk | **Tvilsom antakelse** |

---

## 5. Team ID / Squad Import Findings

| Steg | Status | Detalj |
|---|---|---|
| Team ID-input (ID eller URL) | VERIFIED | `ConnectHero.tsx` trekker ut `entry/(\d+)`. Regex `^\d{1,10}$`. |
| Ugyldig format | VERIFIED | Presis lokal melding. |
| Ukjent ID | **BROKEN** | 500 og «Failed to fetch» (ISSUE-007). |
| Manager og lagnavn | VERIFIED | Lagnavn og etternavn («Selvaraj»). Kun etternavn er et bevisst valg. |
| Spillere og squad (15) | VERIFIED | Fra `entry/{id}/event/{current}/picks`. Navn, klubb og pris fra bootstrap. |
| Starting XI, benk, C/VC | VERIFIED | Offisielle `position` og `multiplier` vises i live-visning og på My Team. Modellens XI vises separat på Overview («Model lineup from your squad»). |
| Bank / lagverdi | VERIFIED | Bank 0,1, verdi 101,7, likt på Overview og Plan (`data.team.bank` brukes først). |
| Free transfers | VERIFIED med forbehold | Utledes fra transfers og chips. Merkes «estimated». Override fungerer og er knyttet til GW. Regelen for WC/FH må verifiseres (L12). Bytter etter fristen er usynlige (ISSUE-015). |
| Chips | VERIFIED | Korrekt per halvdel. Aktiv chip i target-GW låser alle. |
| Gameweek | VERIFIED | Header «GW6 LIVE · GW7 DEADLINE» er korrekt. I simuleringen var `meta.event` (fra entry, = 6) og `meta.current_event` (5) forskjellige. To kilder til «gjeldende GW» (se §12). |
| Transferhistorikk | Delvis | Brukes til FT og Review, men vises ikke som historikk. |
| Analyse | **BLOCKED** i dag (ISSUE-001). I simuleringen VERIFIED, men med logikkfeilene over. |
| Konsistens mellom sider | Delvis | Bank, verdi, captain og FT er like på Overview og Plan. **Transferanbefalingen** er forskjellig mellom `decision.transfers` og det UI viser (ISSUE-004). Siden UI kun bruker én av dem, ser brukeren ikke konflikten, men ethvert annet API-konsument gjør det. |

---

## 6. Transfer Engine Findings

- **Hard-regler (budsjett, posisjon, 3 per klubb):** VERIFIED korrekt. MILP-en er rask (< 1 s for 6 løsninger).
- **Realisme:** svak. Typiske anbefalinger:
  - **Palmer (9,7) → Rashford (7,0)** i fem lag. Rashford har 53,6 xMins i GW6-prognosen. Å selge en premium for en rotasjonsutsatt spiller fordi 5-GW-scoren er litt høyere er ikke noe en erfaren manager ville gjort uten bedre underlag.
  - **Benk-GK-bytter** (ISSUE-002).
  - **Benk-oppgraderinger med hit** (ISSUE-008).
  - **Scenario C** (dårlig fixture, men sterk på sikt): delvis håndtert, fordi 5-GW-vekting brukes. Fixture-sensitiviteten er så lav (L9) at dette sjelden blir avgjørende.
- **Scenario B (skade):** salg av skadet spiller håndteres, men overdrevent (ISSUE-005). Et 75 %-flagg (Schade) gir anbefalt salg.
- **Scenario D (lite bank):** reglene håndheves, men salgsprisen er estimert (ISSUE-011).
- **Scenario E (flere FT):** bruker alltid alle (ISSUE-003).
- **Scenario F (differensialer):** eierandel brukes ikke i noen beslutning. Motoren er nøytral mellom template og differensial, uten EO-hensyn. Det er et produktvalg, men det er ikke synliggjort.
- **Scenario G (wildcard):** WC anbefales når den er tilgjengelig, uansett lagets tilstand (ISSUE-006).

---

## 7. Captain Findings

- **Egen captain-logikk** finnes (`_captain_score`), men den er bare en omvekting av samme `predicted_points`. Det er ingen ceiling- eller floor-modell.
- **Faktorene** er dekket som følger:

  | Faktor | Dekning |
  |---|---|
  | Forventede poeng, minutter, tilgjengelighet, FDR | Brukes, men dobbeltelles |
  | Hjemme/borte | Bare via modellen |
  | Straffe, dødball, xG/xA, rotasjon (utover minutter) | Ikke brukt |
  | Ceiling | Ikke brukt |
  | Captain over flere GW (DGW, TC-planlegging) | Ikke brukt |

- **«Beste spiller ≠ beste captain»** er teoretisk mulig, men skjer i praksis bare gjennom minutt- og fixture-faktorene.
- **Visekaptein** er ganske enkelt nummer 2 i samme rangering. Det er OK, men visekapteinen bør helst ha en annen kamp (tidspunkt og risiko) enn kapteinen.
- **UI** viser captain-rangering med score. Det er bra, men scoren («5,24») er en abstrakt enhet uten forklaring.

## 8. Expected Points / ML Findings

**Dataflyt:** `merged_gw.csv` (historikk) og `fixtures` går gjennom `build_feature_frame`, som gir 17 features: pris, hjemme, poeng siste 3/5, minutter, starter, mål, assist, BPS, ICT-komponenter, `history_gw_count`, FDR og posisjon. Deretter `HistGradientBoostingRegressor`, så `clip ≥ 0`. Til slutt `× availability_multiplier` (kjøretid), og så FDR-skalering til GW2–5.

- **Lekkasje:** CODE. Kausalitetssjekken og `history < gw` ser korrekte ut. Ingen tegn til target-lekkasje. Kjent forbehold: historisk FDR er et snapshot fra sesongslutt (dokumentert).
- **Modell mot baseline** (`models/fpl_model_v4.pkl.validation.json`):

  | | MAE | RMSE | Spearman | Top-10 faktiske poeng |
  |---|---|---|---|---|
  | Modell | 1,256 | 2,230 | **0,618** | 6,06 |
  | Baseline (`points_avg_5`) | 1,350 | 2,650 | **0,667** | 3,46 |

  - Modellen er bedre på absolutt feil og på topp-10, men **rangerer spillere dårligere enn baselinen** (Spearman). Det samme gjelder i rolling-origin-foldene (2023-24: 0,670 mot 0,686).
  - FPL-beslutninger er rangeringsbeslutninger, så sertifiseringen bør kreve at modellen ikke er dårligere på rangering, eller i det minste rapportere det.
  - Holdout er bare GW1–5 (3216 rader), og GW1 har ingen historikk.
- **Kalibrering:** Prognosene er sterkt komprimert (maks 5,5, median 0,75). Det er greit for EV-summer, men gjør captain og differensialer dårlig skilt. Kalibrering per desil er ikke rapportert.
- **Manglende signaler som finnes i offentlige data:** `expected_goals`, `expected_assists`, `expected_goal_involvements` (bootstrap), lagstyrke (`strength_*`), straffe- og dødball-rekkefølge (`penalties_order` osv.). Understat-data lastes ned (`historical_data/*/understat`), men brukes ikke.
- **Horisont:** ingen egen prognose per GW (L9). Dette er den største svakheten for et produkt som fremhever «5-GW».
- **Tilgjengelighets-multiplikator** er en regel og kan ikke valideres (dokumentert). Den smitter over horisonten (ISSUE-005).
- **Drift-overvåking:** `forecast_checks.csv` inneholder bare GW3 (legacy). For GW4 og GW5 finnes ingen sjekker fordi det ikke fantes artefakter. README sier drift «shows up within a week», men det er ennå ikke demonstrert.

## 9. Data Quality Findings

- Offisielle navn, priser, posisjoner og klubber legges over prognosene ved hver request. Bra.
- Prognose-CSV-en har 667 rader, likt med bootstrap.
- `availability` normaliseres til tre nivåer. Risikomodulen forventer flere (L8).
- `rotation_risk` er alltid tom. Kolonnen finnes i kontrakten, men fylles aldri.
- Salgspris er estimert (ISSUE-011).
- Gjeldende GW har flere kilder (§12).
- `requirements-pipeline.txt`-kommentaren refererer til `fpl_model_v3.pkl`, mens v4 er i bruk. `PROJECT_HANDOFF.md` sier «no scheduler runs it yet», men workflowen finnes. `ARCHITECTURE.md` beskriver et «AI / ChatGPT Layer» som ikke finnes. Dokumentasjonen er ute av synk med koden.

## 10. Frontend / UX Findings

**Sterkt:** visuell kvalitet, hierarki («MAKE THE MOVE», ut/inn-kort, Next GW / 5-GW / Hit / Net), mobil uten overflyt, pitch-editor, kildemerker, «Not right? Set yours».

**Problemer:**

1. Ukjent ID gir «Failed to fetch» (ISSUE-007).
2. Låst plan gir generisk «No plan available … Try refreshing» og sjargong i banneret (ISSUE-001 og ISSUE-012).
3. Tekst som lover mer enn koden gjør: «clears its threshold after cost and uncertainty» og «only proposes a hit when …» (ISSUE-008 og ISSUE-009).
4. «High confidence» vises alltid. Signalet er verdiløst og villedende (ISSUE-006).
5. Captain-score uten enhet eller forklaring.
6. «Squad Outlook»-totalene er minutt-justerte, mens cellene viser rå xP, så kolonnene summerer ikke synlig til totalen. Haalands celler 5,5 + 6,9 + 6,0 + 6,4 + 6,0 = 30,8 stemmer, men for Schade er cellene 15,4 og totalen 13,5.
7. Rank-grafen viser negativ akse (ISSUE-014).
8. «Updated 4 min ago» rett etter tilkobling (tiden kommer fra cache-`fetched_at`). Det kan forvirre, men er teknisk korrekt.
9. Players-markedet lastes med `limit=50` i dashboardet. `nextGwGain` krever `inXp` fra markedet og blir `null` («—») når innkommende spiller ikke er blant de 50 beste (CODE, `plan.ts:toMoves`).

## 11. Backend / Architecture Findings

- **Ett tungt endepunkt** (`/api/v1/dashboard`) kjører alt (team, live, history, fixtures, players, decision) og polles hvert 60. sekund (ISSUE-013).
- **`_apply_official_player_state`** itererer `iterrows()` over 667 rader på hver request, 3–4 ganger per dashboard (`get_decision`, `get_enriched_player_rankings`, `_live_event_expectations`). Dette er unødvendig CPU-bruk. Vektoriser og cache per (prognoseversjon, bootstrap-tidsstempel).
- **Bootstrap valideres flere ganger** per request (`_validate_prediction_target` 2–3 ganger).
- **`/players/top`** bruker `get_team_fixtures(1, …)` for å finne gjeldende GW (hack, `backend/main.py:772`).
- **Gatewayen** forsøker 4xx på nytt og skiller ikke 503 «game updating» fra annet (ISSUE-007).
- **Feilhåndtering:** ufangede unntak gir ren-tekst-500 uten CORS.

## 12. Duplicate Logic

| Sannhet | Steder |
|---|---|
| Transferrangering | `transfer_analysis.optimize_transfer_plan` (MILP, vektet 5 GW) **og** `decision_intelligence._select_horizon_transfer` (`combined_score`) |
| Horisontverdi per spiller | `optimizer/multi_gw.aggregate_multi_gw_value` (vektet) **og** `decision_horizon.player_horizon_projection` (minutt-justert, uvektet) |
| Tilgjengelighet fra FPL-status | `backend/main._apply_official_player_state`, `frontend/lib/fpl/rules.availabilityFromStatus`, `frontend/lib/model/plan.riskRank`, `decision_risk.player_risk` (andre labels) |
| Formasjonsregler | `fpl_rules.py`, `optimizer/starting_xi.py`, `optimizer/squad_optimizer.py`, `frontend/lib/fpl/rules.ts` |
| Hit-kostnad | `transfer_analysis.py` (`hit_cost`), `optimizer/transfer_optimizer.TransferOptimizationConfig`, `frontend/lib/fpl/rules.hitCost` (frontend beregner hit på nytt fra antall moves) |
| Gjeldende/target-GW | `main._get_prediction_event`, `main._validate_prediction_target`, `planning_state.build_planning_state`, `team_service._get_current_event`, `live_service._current_event`, `fixture_service` (`current_event`/`next_event`) |
| Posisjonsnormalisering GK/GKP | `backend/main` (1→"GK"), `forecast.POSITIONS`, `transfer_analysis` (`replace({"GKP":"GK"})`), `frontend/lib/fpl/rules.normalizePosition` |
| Prediksjonslasting | `main._load_predictions`, `main.load_predictions`, `backend/data_loader.load_players`, `review_service.select_review_prediction_file` |
| Team-oppslag | `main.get_official_team`, `main.get_team_data`, `main.get_team` (`/team/{id}`) |

## 13. Dead / Unnecessary Functionality

Kontrollert med grep etter importer og kall. Ingenting er slettet.

**SAFE TO REMOVE** (ingen importer i produksjon eller tester):

- `models/prediction_engine.py`: ingen importer, bruker `fpl.db`.
- `fpl.py`: SQLite-skript uten importer.
- `decision_intelligence._insights`-evidensen `net_gain` (feil nøkkel). Rett den i stedet for å fjerne den.
- `decision_risk`-mappingene for statusene `NEWS`, `MINOR_RISK` og `MAJOR_RISK` og rotasjonsstraffen, så lenge ingen produsent finnes (L8). Alternativt: implementer produsenten.

**REQUIRES INVESTIGATION:**

- `app.py` (Streamlit, 1880 linjer) og `app_team.py`: importeres bare av tester (`tests/test_app.py` m.fl.). `streamlit` ligger i rot-`requirements.txt`.
- `fpl.db` og `data/update_data.py`: knyttet til legacy-Streamlit.
- `feature_engine.py` og `transfer_in.py`: importeres bare av tester.
- Backend-ruter som frontend ikke bruker: `/team/{id}`, `/team/{id}/history`, `/team/{id}/live` (brukes internt av dashboardet, men selve ruten kalles ikke av frontend), `/players/top`, `/live/players`, `/fixtures/team/*`, `/api/decision/{id}`, `/api/v1/plan/{id}` (ignorerer også FT-override), `/api/v1/fixtures`. Kontroller eksterne konsumenter før de fjernes eller merkes deprecated.
- `optimal_squad` i decision-svaret: brukes bare til `wildcard_pressure` (ISSUE-006).
- Arkiverte artefakter `gw3_predictions_v11.csv` og `gw6_predictions_v11/v12.csv`: kan være nødvendige for Review (`select_review_prediction_file`). Sjekk før sletting.
- `backtesting/` (D0–D9-rapporter): ikke i request-pathen, men verdifull for å kalibrere ISSUE-003 og ISSUE-006. Behold.
- Utdaterte dokumenter: `CODEX_INSTRUCTIONS.md`, `EXTERNAL_REVIEW_SUMMARY.md`, `BASELINE_HEALTHCHECK.md`, `PROJECT_CONTEXT.md`, `ARCHITECTURE.md` (AI-lag som ikke finnes).

## 14. Missing Functionality

| Feature | Brukerproblem som løses | Gevinst | Kompleksitet | Prioritet |
|---|---|---|---|---|
| Foreløpig prognose for N+1 rett etter fristen | Kan ikke planlegge 3–5 dager i uka | Produktet blir brukbart hele uka | MEDIUM | **P0** |
| XI-bevisst transferverdi | Benk-GK- og benk-oppgraderinger | Riktige transfers | MEDIUM | **P0** |
| Roll mot transfer med eksplisitt rulleverdi | Bruker FT på marginale bytter | Færre bortkastede transfers, korrekt «HOLD» | MEDIUM | **P0** |
| Prognose per GW i horisonten (fixture- og lagstyrke-spesifikk) | 5-GW-tall er nesten flate | Reell fixture-swing og planlegging over flere GW | HIGH | P1 |
| Utledede salgspriser | Forslag kan være umulige i FPL | Gjennomførbare råd | LOW–MEDIUM | P1 |
| Hit-evaluering (FT+1, FT+2) | Hits vurderes aldri | Korrekte −4-beslutninger | LOW (etter P0) | P1 |
| Kalibrert confidence (margin relativt til usikkerhet) | «HIGH» alltid | Tillit når den er fortjent | MEDIUM | P1 |
| Captain-ceiling og -margin | Kan ikke skille trygg og eksplosiv captain | Bedre captain-valg, synlig usikkerhet | MEDIUM | P1 |
| Wildcard/chip-planlegging over flere GW (WC-lag mot beste transfer-plan, BB/TC på DGW-er fremover) | Chips anbefales på regler | Riktig timing av chips | HIGH | P2 |
| Konkrete forklaringer («Hold Saka: 34,1 poeng neste 5 …») | Generisk tekst | Mindre research for brukeren | LOW–MEDIUM | P1 |
| Skadevarsler og nyheter med dato og retur | Uklart hvor lenge en spiller er ute | Riktig hold/sell ved korte skader | LOW | P2 |
| Prisendringsvarsler | Taper verdi | Liten, men ukentlig nytte | MEDIUM | P3 |
| EO og eierandel i strategi (template-risiko) | Rank-beslutninger | Bedre for jakt på rank | MEDIUM | P3 |

## 15. Automated Tests We Are Missing

1. **Transfer**: «benk-GK-bytte anbefales aldri når GK1 spiller», og «transfer som bare forbedrer benk har ~0 gevinst».
2. **Roll**: et sterkt lag der beste gevinst er under rulleverdien gir `ROLL`. Med FT=2 og én god og én marginal transfer brukes bare én.
3. **Konsistens**: `decision.transfers.recommended_transfers == intelligence.transfer_strategy.selected_transfers` (eller felt fjernet).
4. **Horisont**: en spiller med 0 % sjanse i GW1 har > 0 i GW3–5. Blank i base-GW gir ikke 0 i fremtidige GW-er.
5. **Hit**: en hit anbefales bare når netto XI-gevinst over horisonten > 4 + margin. FT=0 med benk-oppgradering gir HOLD.
6. **Confidence** varierer: liten margin gir LOW eller MEDIUM.
7. **Wildcard** anbefales ikke for et sunt lag.
8. **Captain**: `_captain_score` straffer ikke tilgjengelighet to ganger. Forsvarer rangeres ikke over angriper med høyere ceiling.
9. **Team ID**: ukjent ID gir 404 JSON med CORS-header. Upstream 5xx gir 502 JSON. 4xx forsøkes ikke på nytt.
10. **Gameweek state**: dashboardet mellom fristen og ferdig GW gir foreløpig plan eller en spesifikk feilkode.
11. **Salgspris**: utledet fra transferhistorikk (kjøp, prisøkning, halvering nedover).
12. **Frontend**: plan-siden viser feilkode-spesifikk tekst. Ukjent ID viser «Team not found». E2E-røyktest (Playwright) av connect → overview → plan mot en fixture-backend.

## 16. Recommended Development Order

### Phase 1: Correctness (må fikses først)

- ISSUE-002: XI-bevisst objektiv.
- ISSUE-003: rulleverdi og HOLD/ROLL.
- ISSUE-004: én rangering og entydige felt.
- ISSUE-005: horisonten fra `ml_prediction`.
- ISSUE-006: aksjon, confidence og WC.
- ISSUE-009: feil nøkkel og usanne tekster.

### Phase 2: Reliability

- ISSUE-001: foreløpig prognose.
- ISSUE-007: 404 og JSON-feil.
- ISSUE-012: feilkoder.
- ISSUE-013: polling og caching.
- E2E-røyktest.

### Phase 3: Decision Quality

- ISSUE-008: hits.
- ISSUE-011: salgspriser.
- ISSUE-010: captain-ceiling.
- Prognose per GW og lagstyrke.
- xG og xA.
- Sertifisering som rapporterer Spearman.
- Backtest-kalibrert rulleverdi og confidence.

### Phase 4: Product UX

- Konkrete forklaringer.
- Captain-forklaring.
- Squad Outlook-totaler.
- ISSUE-014 og ISSUE-015.
- Markedsdata for alle innkommende spillere.

### Phase 5: Advanced Features

- Chip-planlegging over flere GW.
- Skade- og prisvarsler.
- EO/template-modus.
