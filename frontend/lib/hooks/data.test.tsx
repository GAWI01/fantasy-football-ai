import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import { TeamProvider, useTeam } from "@/app/providers/TeamProvider";
import { makeDashboard, makeFixtureMatrix, makePlayerMarket, makeReview } from "@/test-utils/fixtures";
import { clearResourceCache } from "./useResource";
import { useFixtureMatrix, useMarketProjections, usePlayerMarket, useReview } from "./data";

afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); clearResourceCache(); });

test("a Gameweek and model rollover reloads the market, matrix and latest review", async () => {
  clearResourceCache();
  localStorage.setItem("fpl-ai-team-id", "4242");
  let rolledOver = false;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = new URL(String(input), "http://localhost");
    let body;
    if (url.pathname.startsWith("/api/v1/dashboard/")) {
      body = makeDashboard();
      if (rolledOver) {
        body.meta.current_event = 7;
        body.meta.prediction_event = 8;
        body.meta.prediction_version = "gw8-new";
      }
    } else if (url.pathname === "/api/v1/players") {
      body = makePlayerMarket();
      body.data.players[0].name = rolledOver ? "Fresh market" : "Old market";
    } else if (url.pathname === "/api/v1/fixture-matrix") {
      body = makeFixtureMatrix();
      body.data.start_event = rolledOver ? 8 : 7;
    } else {
      body = makeReview(rolledOver ? 7 : 6);
    }
    return new Response(JSON.stringify(body), { status: 200 });
  });
  function Probe() {
    const { refresh, teamId } = useTeam();
    const market = usePlayerMarket();
    const matrix = useFixtureMatrix();
    const review = useReview(teamId);
    return <>
      <p>{market.data?.data.players[0].name}</p>
      <p>Matrix GW{matrix.data?.data.start_event}</p>
      <p>Review GW{review.data?.data.event}</p>
      <button onClick={() => void refresh()}>Reload dashboard</button>
    </>;
  }
  render(<TeamProvider><Probe /></TeamProvider>);
  await screen.findByText("Review GW6");
  await screen.findByText("Old market");
  rolledOver = true;
  await userEvent.click(screen.getByRole("button", { name: "Reload dashboard" }));
  expect(await screen.findByText("Fresh market")).toBeInTheDocument();
  expect(await screen.findByText("Matrix GW8")).toBeInTheDocument();
  expect(await screen.findByText("Review GW7")).toBeInTheDocument();
});

test("incoming-player forecasts from a different Gameweek cannot enter the current plan", async () => {
  clearResourceCache();
  localStorage.setItem("fpl-ai-team-id", "4242");
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const body = String(input).includes("/dashboard/") ? makeDashboard() : makePlayerMarket();
    if ("players" in body.data) Object.assign(body.data, { prediction_event: 8 });
    return new Response(JSON.stringify(body), { status: 200 });
  });
  function Probe() {
    const { dashboard } = useTeam();
    const market = useMarketProjections(Boolean(dashboard));
    return <p>{market.data ? market.byId.get(201)?.predicted_points != null ? "Incoming forecast present" : `Projection unavailable for ${market.byId.get(201)?.name}` : "Loading projections"}</p>;
  }
  render(<TeamProvider><Probe /></TeamProvider>);
  expect(await screen.findByText("Projection unavailable for Castellano")).toBeInTheDocument();
});
