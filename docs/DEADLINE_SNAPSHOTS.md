# Pre-deadline public data archive

`python -m historical_data.deadline_snapshots` acquires the full public FPL
`bootstrap-static` response and, only when a capture is due and missing, the
full public `fixtures` response. It does not request manager or team-entry
data. Files default to ignored `output/deadline-snapshots/`; raw snapshots must
stay outside Git.

The nearest future event deadline is the target, independently of upstream
`is_next`. Every bundle preserves the raw JSON responses, source URLs, actual
UTC request start and completion times, SHA256 hashes, season, target event,
deadline, actual seconds remaining, and intended capture time. The manifest
also records the official `is_current` and `is_next` event IDs as the
`ep_this` and `ep_next` mappings. Empty or multiple mappings remain explicit;
neither forecast field is assumed to describe the target event.

## Capture timing and failure behavior

The scheduled capture targets are 24 hours and 90 minutes before the deadline.
An acquisition may start from 15 minutes before to 45 minutes after its intended
capture time: respectively 24h15m–23h15m and 1h45m–45m before the deadline,
including the boundaries. This permits normal 30-minute scheduling jitter
while bounding late captures. The manifest records the actual time rather than
backdating a delayed response. Source acquisition, raw-file writes and the final
pre-publication time check must finish before the target deadline. Publication
and Release upload can happen later without changing the recorded input time.
If the deadline passes during acquisition, the recorder fails closed instead
of switching to a later event or labelling the response pre-deadline.

Requests identify this archive in their User-Agent, use 5-second connect and
20-second read timeouts, and permit at most three attempts per source with
1- and 2-second retry delays. Read timeout bounds an individual stalled read,
not a guaranteed total response duration. The workflow has a 10-minute limit.
Invalid responses, exhausted retries, backwards clocks, crossed deadlines and
failed writes produce no completed output bundle.

Bundles are staged in hidden temporary directories and become available only
after a successful directory rename. An exclusive local reservation prevents
concurrent writes to a scheduled season/event/window. Existing bundles are
never overwritten. Ordinary failures clean up reservations and partial writes;
a killed process can leave hidden partial directories or a lock. Inspect these
before removing them and retrying; they are not complete bundles. Only a
successfully returned directory containing its manifest is eligible for upload.

GitHub runs `.github/workflows/deadline-snapshots.yml` at minutes 7 and 37 with
serialized runs. Scheduled workflows run from the default branch and can be
delayed, dropped, disabled by repository inactivity, or held in a concurrency
queue. Captures outside the stated window are skipped. No exact-time,
every-deadline, atomic-upstream-view or universally leak-free guarantee is made.
The two endpoint responses are sequential, and FPL can update them independently.
Use per-source times and the event mappings when evaluating forecast provenance.
This archive supplies future evidence; it does not repair older historical data,
retrain a model or certify already-inspected evaluation results.

## Durable storage and retrieval

The workflow checks existing archive asset names before acquisition. It fetches
bootstrap metadata once per run, then skips fixtures when outside the capture
windows or when that scheduled capture is already present locally or on a
Release. Release-index failures stop the workflow rather than assume an empty
archive. Completed bundles are compressed and uploaded to the season-specific
GitHub prerelease `data-archive-2026-27` (and corresponding later seasons).
Assets are named
`snapshot-2026-27-gw8-24h-20261016T100006Z-RUN_ID-RUN_ATTEMPT.tar.gz`.
The timestamp describes bundle completion; the manifest retains its full
precision. Run ID and attempt keep uploads unique. Uploads never use
`--clobber`; an upload failure leaves any existing asset intact. Releases retain
assets until an owner explicitly removes them; the workflow has no pruning.
No new storage service or credentials are required beyond the repository's
`GITHUB_TOKEN` with `contents: write`. Git contains only code and documentation.

Download through the repository's Releases page or GitHub CLI:

```bash
gh release download data-archive-2026-27 --repo OWNER/REPO \
  --pattern 'snapshot-2026-27-gw8-24h-*.tar.gz' --dir output/retrieved
tar -xzf output/retrieved/SELECTED_ASSET.tar.gz -C output/retrieved
```

Read `manifest.json`, verify each source file's SHA256 against its manifest
entry, and check source completion times against `deadline_time` before use.
Repository access controls govern Release visibility; assets in a public
repository are public. Treat provider data ownership and permission separately
from repository visibility and content hashes.

For a local read-only inspection at any pre-deadline time:

```bash
python -m historical_data.deadline_snapshots --help
python -m historical_data.deadline_snapshots --force --output-dir output/deadline-inspection
```

`--force` still refuses deadline crossing. It creates a unique `manual` bundle
with no claimed 24h/90min target time. The CLI prints one JSON result containing
the completed bundle path, or `captured: false` when nothing is due. Local use
does not upload or publish. `--archived-assets FILE` optionally supplies a JSON
array of existing Release asset names for scheduled deduplication.

## Data-use boundaries

These endpoints are publicly accessible official Premier League/FPL sources;
public accessibility does not establish an open licence or commercial reuse
permission. Existing launch review requirements and Vaastav's separate
repository permission and attribution remain in [DATA_SOURCES.md](DATA_SOURCES.md).
This archive is provenance infrastructure under those existing boundaries.
Re-review provider terms, request volume, branding, attribution and redistribution
permissions before enabling it for commercial/public deployment. A hash proves
file identity, not licensing or forecast validity.
