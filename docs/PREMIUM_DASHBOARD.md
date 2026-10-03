# Premium dashboard foundation

FPL AI is a public-Team-ID decision product. It reads public Fantasy Premier League data, combines it with versioned local predictions, and never performs actions on the official FPL account.

## Product surfaces

- **Overview:** a Gameweek cockpit. Before the deadline (decision mode) it leads with one plan card: transfer or HOLD, captain, vice-captain, projected score, chip, bench order and the main risk, with Why and Compare one tap away. While a Gameweek is live it switches to live points, captain contribution, played/playing/to-play progress, your matches, returns and an auto-sub watch. After a deadline the old plan is marked read-only.
- **My Team:** all 15 players on a pitch with projected or live values, C/VC, availability flags and a player sheet (xP, xMins, start chance, price, form, ownership, five-GW outlook, model read, official news). Lineup simulation by drag and drop on desktop or tap-to-swap on touch; only legal formations are offered and nothing is sent to FPL.
- **Plan & Transfers:** transfer decision with OUT→IN, next-GW gain, five-GW gain, hit cost and five-GW net; scenario comparison including hit checks; captaincy from owned players only; conservative chip advice; squad heatmap; minutes risk and local plan history.
- **Players:** market table with search, position and price filters, sortable columns, next three fixtures, a shareable four-player shortlist and a comparison sheet. `/explore` redirects here.
- **Fixtures:** every club's run with explicit home/away, blanks, doubles and a derived run score; owned clubs highlighted.
- **History & Review:** official rank and points history plus the per-Gameweek review against the model file saved before that deadline.
- **Settings:** locally stored Team ID, season goal, runtime provenance and the data-label guide.

Club identity uses an original kit system (club-inspired colours, generic patterns, initials). It deliberately avoids official crests, shirts, sponsors and league branding.

## Data contract

The frontend uses `/api/v1/dashboard/{team_id}` as its resilient aggregate. A required team failure stops the request; optional live, history, fixtures, players or decision failures return a degraded response with area-specific errors.

Every surface labels its data class (Cached is shown when the official service did not respond and the last good copy is used):

- `Live`: current event/player output.
- `Official`: official FPL manager, squad and fixture state.
- `Model`: versioned prediction or optimizer output.
- `Derived`: calculations made from the above.

The prediction manifest is `historical_data/current_data/manifest.json`. Publishers replace it atomically only after the full prediction artifact exists.

## Local development

Backend, from the repository root:

```powershell
python -m pip install -r requirements.txt -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
Copy-Item ..\.env.example .env.local
pnpm install
pnpm dev
```

Open `http://localhost:3000` and enter the numeric Team ID visible in the official FPL URL. Without `NEXT_PUBLIC_API_URL`, the frontend deliberately uses a deployment-safe same-origin API path; the local `.env.local` points it to `http://127.0.0.1:8000`.

## Production configuration

Set `NEXT_PUBLIC_API_URL` to the HTTPS API origin during the frontend build. Set `FPL_AI_CORS_ORIGINS` to a comma-separated list of exact HTTPS frontend origins. Wildcard CORS is rejected.

Recommended process commands:

```text
API:      python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
Frontend: pnpm build && pnpm start
```

Use `/health` for liveness and `/api/v1/status` for official/model readiness. Application instances are stateless apart from their in-process upstream cache; add a shared cache only when multiple replicas make it necessary.

## Verification

```powershell
python -m pytest tests backend/tests -q
cd frontend
pnpm test
pnpm lint
pnpm exec tsc --noEmit
pnpm build
```

No deployment should be described as ready until these commands and a real public Team-ID smoke test have passed in that environment.
