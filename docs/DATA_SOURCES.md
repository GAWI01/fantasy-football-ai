# Data-source register

## Official Fantasy Premier League API

FPL AI currently uses public Fantasy Premier League endpoints for bootstrap/player metadata, fixtures, event live data and public manager/team history. Data is cached behind the backend gateway with request timeouts and stale fallback, so each browser does not independently hammer the upstream service.

Before commercial/public launch, the project owner must re-review the Premier League/FPL website terms, branding rules, acceptable request volume, attribution expectations and any restrictions on commercial reuse. The current implementation should not be interpreted as legal approval.

## Prediction artifacts

Model output is generated inside this project and published with a versioned manifest. A publication timestamp certifies when an artifact was published, not that its inputs are licensed or that its model was validated. The UI labels these values `Model`, never `Live` or `Official`. Forecasts from `gw6_predictions_v12.csv` onwards (now `v13`, model v4) carry the certified model's hashes, its validation report and the SHA256 of every input file; earlier artifacts (GW3 v11, GW6 v11) do not and remain unverified.

## Historical FPL and Understat data

Offline training and mapping scripts use [Vaastav's Fantasy-Premier-League repository](https://github.com/vaastav/Fantasy-Premier-League). The retained FPL seasons and Understat files are separate data dependencies. The upstream software licence does not establish permission from the original FPL/Understat data owners for downstream data reuse. No provider agreement, pinned source revision or complete retrieval/hash register is present in this repository.

Before regenerating a model for release, record the exact source revision, retrieval time, input checksums, attribution and applicable data-use permission. Understat player-name/ID mapping is currently an offline path; its football statistics are not established live model inputs. Do not describe these sources as approved until evidence exists.

Historical scraped `xP` has an upstream lookahead warning and is never used. Feature contract v4 uses completed-Gameweek history only; the model was retrained and evaluated on that basis (docs/MODEL_PIPELINE.md). Its validation report records SHA256 checksums of every training and test input, not the upstream source revision or retrieval time.

## Product boundary

The MVP does not collect FPL passwords, write to official FPL accounts or automate transfers/chips. Any future source must be added to this register with ownership, license/terms, attribution, refresh interval, failure mode and retention policy before it is enabled in production.
