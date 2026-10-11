# Contributing

Thanks for helping improve Fantasy Football AI. It is a small, free,
non-commercial project, so keep changes focused and easy to review.

## Before you start

- Bugs and ideas: open an issue with the matching template first, so we can
  agree on the approach before you write code.
- Read [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for how the pieces fit
  and [docs/LESSONS_LEARNED.md](../docs/LESSONS_LEARNED.md) for the rules this
  project follows.

## Setup

See "Run it locally" in the [README](../README.md). In short: Python 3.12+ for
the API and engine, Node.js 22+ with pnpm for the app.

## Making a change

1. Branch from `master`.
2. Keep the decision in the backend: the frontend shows the engine's plan and
   never recomputes it.
3. Add or update tests for what you change.
4. Run the same checks as CI:

   ```bash
   python -m pytest
   cd frontend && pnpm test && pnpm lint && pnpm exec tsc --noEmit && pnpm build
   ```

5. Open a pull request using the template. CI must be green before merging.

## Data and privacy rules

These are not optional; the repository and the app are public.

- Never commit real people's data: no real manager names, team names, league
  names or IDs in tests, fixtures, recordings or screenshots. Use invented
  names and pseudonymise recorded API responses.
- Never show or return managers' personal names in the app or API.
- Do not add data sources without the owner's permission and attribution; see
  [docs/DATA_SOURCES.md](../docs/DATA_SOURCES.md) and
  [DATA_NOTICE.md](../DATA_NOTICE.md).
- No Premier League, FPL or club logos, crests or photos.
- No secrets in the repository. Configuration goes in environment variables.

## Licence

By contributing you agree that your code is released under the
[MIT licence](../LICENSE). Data is not covered by that licence.
