"""Record a decision-benchmark snapshot from the live FPL API.

    python -m benchmark.record_snapshot NAME EVENT TEAM_ID [TEAM_ID ...]

Runs the dashboard for each team as if just before EVENT's deadline. Any
upstream URL not yet in the snapshot is fetched live once and stored raw.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("FPL_AI_UPSTREAM_MAX_PER_MINUTE", "1000")

import requests  # noqa: E402

from backend import fpl_gateway  # noqa: E402
from benchmark.harness import _Response, replay, save_snapshot  # noqa: E402


def main(argv: list[str]) -> None:
    name, event, team_ids = argv[0], int(argv[1]), [int(x) for x in argv[2:]]
    responses: dict = {}
    session = requests.Session()

    def fetch(url: str):
        if url not in responses:
            response = session.get(url, timeout=20, headers={"User-Agent": fpl_gateway.USER_AGENT})
            responses[url] = response.json() if response.status_code == 200 else None
        return responses[url]

    fetch(f"{fpl_gateway.FPL_API}/bootstrap-static/")
    from fastapi.testclient import TestClient
    from backend.main import app
    for _ in range(2):  # the second pass replays only; it must need nothing new
        before = len(responses)
        with replay(responses, pre_deadline_event=event):
            gateway = fpl_gateway.default_gateway
            replayed = gateway._http_get

            def http_get(url, **kwargs):
                if url not in responses:
                    fetch(url)
                return replayed(url, **kwargs)

            gateway._http_get = http_get
            client = TestClient(app)
            for team_id in team_ids:
                status = client.get(f"/api/v1/dashboard/{team_id}").status_code
                print(team_id, status)
        print("new responses:", len(responses) - before)
    print(save_snapshot(name, responses))


if __name__ == "__main__":
    main(sys.argv[1:])
