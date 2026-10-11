# Data-source register

## Official Fantasy Premier League API

FPL AI currently uses public Fantasy Premier League endpoints for bootstrap/player metadata, fixtures, event live data and public manager/team history. Data is cached behind the backend gateway with request timeouts and stale fallback, so each browser does not independently hammer the upstream service.

Before commercial/public launch, the project owner must re-review the Premier League/FPL website terms, branding rules, acceptable request volume, attribution expectations and any restrictions on commercial reuse. The current implementation should not be interpreted as legal approval.

## Prediction artifacts

Model output is generated inside this project and published with a versioned manifest. A publication timestamp certifies when an artifact was published, not that its inputs are licensed or that its model was validated. The UI labels these values `Model`, never `Live` or `Official`. Forecasts from `gw6_predictions_v12.csv` onwards (now `v13`, model v4) carry the certified model's hashes, its validation report and the SHA256 of every input file; earlier artifacts (GW3 v11, GW6 v11) do not and remain unverified.

## Historical FPL and Understat data

Offline training and mapping scripts use [Vaastav's Fantasy-Premier-League repository](https://github.com/vaastav/Fantasy-Premier-League).

**Permission from the repository author.** On 2026-10-11, Vaastav Anand
confirmed by direct message that this project may use the data, provided it
gives attribution that the data comes from
https://github.com/vaastav/Fantasy-Premier-League. That attribution is shown
in the README ("Data and credits") and in the app's footer on every page. Keep
both if either is reworded.

The retained FPL seasons are a separate data dependency. Vaastav's permission covers his repository; it does not establish permission from the original FPL data owners for downstream reuse. No provider agreement, pinned source revision or complete retrieval/hash register is present in this repository.

Before regenerating a model for release, record the exact source revision, retrieval time, input checksums, attribution and applicable data-use permission. Understat data and the scripts that fetched it were removed on 2026-10-11: Understat has no open licence and its data was never a model input. Do not describe these sources as approved until evidence exists.

Historical scraped `xP` has an upstream lookahead warning and is never used. Feature contract v4 uses completed-Gameweek history only; the model was retrained and evaluated on that basis (docs/MODEL_PIPELINE.md). Its validation report records SHA256 checksums of every training and test input, not the upstream source revision or retrieval time.

## Personal data

- No user database. A Team ID is used per request and cached in memory with the FPL response for minutes.
- Managers' personal names are never returned by the API or shown; mini-leagues show team names only.
- Application logs replace numeric IDs in paths with `{id}`; uvicorn's access log (client IP plus full path) is off (`Dockerfile.backend`).
- Each client IP is limited per minute (`backend/rate_limit.py`, `FPL_AI_RATE_LIMIT_PER_MINUTE`, default 120).
- The benchmark snapshot of recorded teams is pseudonymised: synthetic IDs 9100001-9100011, no names, regions, badges or league memberships. Only the project owner's own team keeps its real ID.
- The public notice is the app's [Privacy and terms](https://fantasyfootball-ai.vercel.app/privacy) page (`frontend/app/privacy/page.tsx`); keep it in step with the code.

## Product boundary

The MVP does not collect FPL passwords, write to official FPL accounts or automate transfers/chips. Any future source must be added to this register with ownership, license/terms, attribution, refresh interval, failure mode and retention policy before it is enabled in production.
