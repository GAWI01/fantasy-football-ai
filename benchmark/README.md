# Decision benchmark

Replays official FPL responses recorded for real teams through the real API,
so engine versions can be compared on identical inputs.

- `snapshots/gw6_pre_deadline.json.gz`: responses for the 12 teams of the
  2026-10-11 audit, seen just before the GW6 deadline.
- `data/gw6/`: the pinned GW6 forecast, manifest, fixtures and clubs.
- `results/`: summaries before and after Phase 1.

```bash
python -m benchmark.run --json out.json          # summarise every case
python -m benchmark.record_snapshot NAME EVENT TEAM_ID ...   # record a new snapshot
```

`tests/test_decision_benchmark.py` pins the decision invariants on a subset.
