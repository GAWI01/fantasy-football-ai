# Overlevering til Claude: prognoser, planlegging og deadline-snapshots

Kodecommit `8b6f245` beholdes uendret og er ikke rebaset eller merget med master.
Denne filen legges til i en separat commit: `Add handoff notes for Claude`.
Claude håndterer konflikten mot PR #62, nye integrasjonstester, CI, merge og
kontroll av Vercel/Railway.

**Avklaring før merge:** Snapshot-workflowen slik den står, laster rå FPL-data
opp som offentlige GitHub-release-vedlegg i dette offentlige repoet. Arkivet er
ikke privat. Claude må vurdere og eventuelt endre lagringen før merge; denne
overleveringscommiten endrer bare dokumentasjonen. Ingen snapshots er lastet
opp av Codex.

## 1. Patch og commits

Fil: `codex-changes.patch` (132 988 bytes).
SHA256: `dd616cbd7bb4f75ede2304cdd583e424f9aac93a16e0ab0954c1a57b655e522b`.

Etter read-only fetch av master kjørte jeg:

```bash
git format-patch origin/master..HEAD --stdout > /workspace/codex-changes.patch
```

Den opprinnelige patchen inneholder hele kodeendringen over origin/master,
med én commit:
`8b6f2455e74a68607b896dc7488d16ac7987e32c` — Fix transfer-plan consistency and archive deadline-time data.
Ved generering av den opprinnelige patchen var arbeidstreet rent, og ingen
remote-gren, PR, CI-kjøring, merge, release-opplasting eller produksjonsutrulling
var opprettet av Codex. Dokumentasjonscommiten med denne filen kommer i tillegg
til kodecommiten. Push og PR forsøkes separat, uten merge eller kodeendringer.

## 2. Base og konfliktintensjon

`git merge-base HEAD origin/master`:
`2ebc8379e27c01c8065f9057c21378b9131506ce` (merge av PR #61).

Etter fetch er origin/master:
`b8de9e0a10864f5205e8d6e2038bda0fdab9b657`.
Min gren er ikke rebaset på denne; patchen er for portering til oppdatert master.

Av de tre spesielt nevnte filene har jeg bare endret
`frontend/components/plan/PlanWorkspace.tsx`. `ReviewWorkspace.tsx` og
`primitives.tsx` er uendret i min commit.

Behold PR #62s faner, Historikk og innstilling for datamerkelapper. Ikke
restaurer hele det gamle Plan-oppsettet ved konfliktløsning. Flytt disse
endringene inn i riktig tab/component:

- Compare options viser uvektede `projected_net_gain` etter faktiske hits,
  separat fra den vektede `decision_score`.
- Score-regnestykket bruker `weightedGain`/`weightedNet`, ikke de nye
  uvektede `horizonGain`/`horizonNet` i frontendens ScenarioView.
- Rader sorteres etter single-stage decision score. Backendens konservative
  oppfølging kan anbefale en lavere rangert rad; behold anbefalingen og
  forklar venting, ikke påstå at den alltid har høyest single-stage score.
- Label og horizon-grid tekst bruker faktisk horisont i stedet for fast fem.
- HOLD-tekst hevder ikke at alle bytter har dårligere umiddelbar score.
- Transfers-fanen bør beholde NextWeekLine og TwoWeekCard, med framtidige
  bytter uttrykkelig betinget av dagens informasjon.

Relaterte UI-endringer finnes i TwoWeekPlan.tsx, GameweekPlanCard.tsx,
WhySheet.tsx, Overview.tsx (kun faktisk horisont i fotnote), contracts.ts,
lib/model/plan.ts og tests. `features.css` lar den lengre kolonneoverskriften
bryte linjer. Ingen endring i global datamerkelapp-logikk.

## 3. Snapshot-jobben

- GitHub Action: `.github/workflows/deadline-snapshots.yml`.
- Cron i UTC: `7,37 * * * *` (hver halvtime), og `workflow_dispatch`.
- Kjøres fra default branch etter merge, ikke i Railway eller backend.
- CLI: `python -m historical_data.deadline_snapshots`.
- Henter public `bootstrap-static` og `fixtures`; ingen manager/entry-data.
- Planlagte vinduer er rundt 24 timer og 90 minutter før nærmeste framtidige
  deadline. Tillatt start er 15 minutter før til 45 minutter etter nominelt
  tidspunkt. Faktiske UTC-tider registreres; jobben kan bli forsinket eller
  hoppe over vinduet. Kryssing av deadline under innsamling avvises.
- Full rå JSON, kilde-URLer, faktiske hentetider, målrunde, deadline,
  offisielle is_current/is_next-mappinger for ep_this/ep_next og SHA256-er
  ligger i hver bunt.

Lagring: immutable `.tar.gz`-vedlegg på sesongens GitHub prerelease, f.eks.
`data-archive-2026-27`, med timestamp + run-ID + attempt i vedleggsnavnet.
Ingen `--clobber`, pruning eller automatisk utløp; vedlegg ligger til de
slettes. Repoet er offentlig, så vedleggene er offentlige. Rådata går ikke
inn i Git. Lokalt brukes ignorerte `output/deadline-snapshots/`.
Kun ferdig opplastede, ikke-tomme release assets teller i dedupliseringen.

Ingen nye manuelt satte secrets, Railway-volumer, database eller ekstern
lagringstjeneste. Action trenger `contents: write`. Den bruker:

- `GH_TOKEN`, satt fra den innebygde `GITHUB_TOKEN`.
- `GH_REPO`.
- GitHubs innebygde `GITHUB_SHA`, `GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT` og
  `GITHUB_OUTPUT`.

Python: standardbiblioteket og `requests` (allerede prosjektavhengighet).
Workflow installerer requests og bruker runnerens `gh`, `jq`, `tar`, `bash`.
Python 3.13 i workflow. Den nye testen av selve jq-filtreringen trenger `jq`;
hvis jq mangler lokalt, hoppes akkurat den testen over. Den ble kjørt hos meg.

Dokumentasjon: `docs/DEADLINE_SNAPSHOTS.md` og tillegg i
`docs/DATA_SOURCES.md`. Eksisterende kildekreditering og tillatelse er beholdt.
Jobben er ikke aktivert eller eksternt prøvd av meg. Manuell live GW7-kopi
med verifiserte hashes ble bare lagret lokalt, merket manual.

## 4. Cache og API-kompatibilitet

`backend/main.py:_decision_cache_key` lager SHA256 av JSON som inneholder:

- lagets team_id, bank, picks (inkl. salgskontekst) og started_event;
- forecast-fil og generated_at;
- hash av de gjeldende projeksjonene etter offisiell overlay;
- NYTT: hver faktisk framtidig horizon-frame: runde, kolonnenavn og SHA256
  av pandas-radhashene;
- chip_state;
- budsjett, effektive gratisbytter, maksbytter og NYTT horisontlengde;
- offisielle spiller-IDer, priser, status, sjanse for neste runde og nyheter;
- event-IDer og deadlines.

Samme nøkkel brukes for resultat-cache og `_pending` Future. Identiske
samtidige forespørsler deler én beregning; forskjellige nøkler blokkerer ikke
hverandre. Feil caches ikke; senere forsøk kan beregne på nytt. Resultatet
deep-copies før forespørselsspesifikk metadata settes.

Dette er en prosesslokal LRU med maks 256 resultater, uten TTL eller delt
Redis. Invalidation skjer gjennom nye inputhash-nøkler; upstream-gatewayen
beholder eksisterende oppfriskning/stale-håndtering. En Railway-replika deler
ikke cache med en annen replika.

Cache-endringen introduserer ingen nye routes, query-parametere eller
response-envelope. Hele patchen legger derimot til bakoverkompatible felt:

- `projected_gain`, `projected_net_gain` i transfer-output, options,
  alternatives, egne evaluerte bytter og intelligence.transfer_strategy.
- Single-stage: uvektet sum av lineup-gain over rundene sammenlignet med å
  holde hele horisonten; projected_net_gain trekker fra faktiske hits nå.
- Eksisterende `gross_gain`/`horizon_gain`, `net_gain`, `decision_score`,
  `combined_score` og `current_net_gain` beholder sine vektede betydninger.
  `base_projected_points` og `projected_points_after_transfers` er også
  fortsatt vektede, tross navnene.

`transfers.two_week` får horisont/vekter, konservativ selection_policy,
recommended_transfers_now, optimality/search-status, optimality_scope,
budget_assumption og baseline `hold_now_then_optimize`. Sequences får
projected_gain/projected_net_gain, weighted_gain_vs_hold, absolute hit_cost,
risk_margin, roll_value og recommended.

Sekvensenes baseline kan bytte neste uke. Derfor er:

```
projected_net_gain = projected_gain - sequence.hit_cost + baseline.hit_cost
score_vs_hold = weighted_gain_vs_hold - delta_hit - delta_margin + delta_roll
```

Fremhev `recommended`, ikke bare høyeste score/best_transfers_now.
`recommended_transfers_now` kan avvike fra best_transfers_now under den
konservative grensen. Tomme/ufullstendige solves må vise ukjent optimalitet,
ikke en oppdiktet anbefalt rad. Legacy-data uten uvektede felt får null,
ikke vektede poeng forklart som uvektede.

Selve korrekthetsrettingen binder neste ukes solve til den faktiske
anbefalte nåværende troppen for hvert bytteantall. Neste ukes gjenkjøp av en
solgt spiller prises til markedspris. Konservativ policy (kan redusere, aldri
øke antall bytter nå) og distinkte Gameweek-prognoser beholdes. Priser antas
konstante; modellen er ikke retrent og bedre framtidige poeng er ikke bevist.

## 5. Eksisterende skip

`tests/test_optimizer.py::test_optimizer_from_real_predictions_file`
hoppes over fordi `historical_data/current_data/gw2_predictions_v5.csv`
ikke finnes. Melding: `GW2 predictions file does not exist`.

Den var allerede skipped på min basemaster (500 passed, 1 skipped).
Testen er ikke endret i patchen eller mellom basen og b8de9e0; filen mangler
også på oppdatert master. Dette er ikke en ny skip fra mine endringer.

## 6. Verifikasjon og kommandoer

Lokalt: Python 3.12.14, Node 24.19.0, pnpm 11.25.0.
Avhengigheter:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-pipeline.txt -r backend/runtime-requirements.txt pytest httpx
cd frontend
pnpm install --frozen-lockfile
```

Fullkontroll:

```bash
# Fra repo-roten
.venv/bin/python -m pytest -q

# Fra frontend/
pnpm test
pnpm lint
pnpm exec tsc --noEmit
pnpm build
```

Ved bygget hadde jeg `NEXT_PUBLIC_API_URL` satt til lokal replay-backend.
Bruk deres korrekte build-miljø; jeg har ikke endret produksjonsvariabler.

Resultater: Python 541 passed, 1 eksisterende skip, kjent Starlette/httpx
DeprecationWarning. Frontend 142 passed (32 filer); lint, typer og build exit0.

Tillegg: faktisk workflow-jq-uttrykk testet mot ferdige, tomme og starter
assets; workflow-YAML og alle run-blokker kontrollert med bash -n; uavhengig
review godkjent etter dette. Produksjonsbygget i browser mot registrerte
API-svar viste riktig net/score og samme anbefalte sekvens, uten JS-feil,
API-5xx eller document-overflow ved 390px. Screenshots/rå live-kopi er lokale
og ikke i patchen. Replay-tid én registrert tropp: 4.388s kald, 0.660s cache;
dette er ikke en kontrollert før/etter- eller hostet produksjonsmåling.

Ingen kontroller er kjørt på en konfliktløst kombinasjon med PR #62. Claude
må kjøre dem på den endelige integrerte grenen.
