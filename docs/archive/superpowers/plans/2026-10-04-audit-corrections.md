# Four audit fixes

Goal: correct the confirmed audit defects without redesigning the application or adding product features.

Architecture: preserve the existing Next.js frontend, FastAPI API, CSV artifacts and Python decision/model modules. Start from origin/master at 13bf2001b987a5ceac9cd5296e8eff025c3d99bd on fix/audit-corrections.

Tech stack: Python/pandas/PuLP/FastAPI, Next.js/React/TypeScript, pytest/Vitest.

## Global constraints

- Four independently reviewable fix groups, with regression tests for behavior changes.
- Do not include first names in displayed player or manager names; preserve raw identity fields where needed for historical joins.
- No Supabase, authentication, database, provider integration, product redesign, merge, push or deployment.
- Preserve the existing free-transfer override work in PR11.
- Do not relabel or regenerate existing prediction artifacts as certified/current without verified inputs and model provenance.
- Keep historical pipelines and useful legacy references. Do not remove duplicate-looking artifacts without checking their role.
- Missing or mismatched forecasts must remain explicitly unavailable.

## Fix 1: backend data and forecast contracts

Keep official live minutes/form separate from prediction metadata. Use surname/web-name display fields, not first-name concatenation. Correct multi-fixture live classification and metadata. Enforce prediction gameweek compatibility on all decision consumers and attach live availability to decision inputs. Preserve pre-deadline review meaning instead of silently applying hindsight. Add focused API/service regressions and run backend tests.

## Fix 2: transfer and chip calculations

Validate funding and club limits for complete transfer combinations, using the existing solver where practical instead of explosive Cartesian search. Bound chip purchases by the manager's real budget and calculate incremental gains against the owned XI/bench/captain. Apply existing chip eligibility rules accurately. Add hand-calculated budget, club, captain, bench and eligibility regressions; measure solver performance.

## Fix 3: reproducible prediction pipeline

Correct GW-history inputs and preservation of rolling features. Stop same-GW xP from silently entering historical evaluation and avoid claiming incompatible persisted models are newly validated. Make publication fail safely without altering certified files. Correct zero-minute/availability and double/blank-fixture behavior. Keep current artifacts unchanged; document model regeneration/revalidation requirements. Add focused pipeline and publication regressions.

## Fix 4: frontend state, numerical display and build integrity

Keep forecasts and actuals aligned by gameweek; respect chip multipliers and missing predictions. Refresh cached resources on expiry/focus and scope history/overrides to team and gameweek. Ensure overrides work when localStorage is unavailable. Remove misleading unsupported wording, preserve existing layout and features. Fix the Docker copy of the absent public directory and update deployment/audit documentation to reflect verified limits. Add meaningful frontend regressions, run frontend tests/lint/typecheck and a production build.

## Final verification

Run Python and frontend suites, lint, typecheck, frontend production build, runtime artifact validation and git diff --check. Review all changes for scope, names, credentials and accidental files. Deliver four separate local fix commits with exact verification results and remaining operational/model limitations. Do not push or deploy.
