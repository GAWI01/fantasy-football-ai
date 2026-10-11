# Security policy

## Reporting a vulnerability

Please do **not** open a public issue for security problems.

Report privately through GitHub: the repository's **Security** tab →
**Report a vulnerability**. Include what you found, how to reproduce it and
the impact you expect. You will get an answer as soon as possible, normally
within a few days.

Examples of what to report: a way to make the API leak data, bypass the rate
limit, run code on the server, or expose a secret.

## Scope

- The web app (Vercel) and the API (Railway) built from `master`.
- The code in this repository.

The app never logs in to Fantasy Premier League, stores no passwords and keeps
no user database; see the app's
[Privacy and terms](https://fantasyfootball-ai.vercel.app/privacy) page.

## Supported versions

Only the current `master` (what is deployed) receives fixes.
