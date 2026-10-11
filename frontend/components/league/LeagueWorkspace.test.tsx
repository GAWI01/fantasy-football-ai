import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { TeamProvider } from "@/app/providers/TeamProvider";
import { mockApi } from "@/test-utils/mockApi";
import { LeagueWorkspace } from "./LeagueWorkspace";

beforeEach(() => localStorage.setItem("fpl-ai-team-id", "4242"));
afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

const meta = { source: "official", fetched_at: "2026-10-11T12:00:00Z", stale: false, version: null };
const player = (id: number, name: string, extra: object) => ({ player_id: id, name, team_short: "ARS", position: "MID", owners: 1, captains: 0, ownership: 33.3, eo: 33.3, rival_eo: 50, you: null, role: null, next_gw_points: 4.2, ...extra });

function serve(fetchSpy: ReturnType<typeof mockApi>) {
  const route = fetchSpy.getMockImplementation()!;
  fetchSpy.mockImplementation(async (input, init) => {
    const url = String(input);
    const json = (data: object) => new Response(JSON.stringify({ data, meta, errors: [] }), { status: 200 });
    if (url.includes("/api/v1/leagues/")) {
      return json({ team_id: 4242, leagues: [
        { league_id: 9, name: "Big code league", managers: 40000, rank: 100, last_rank: 90, analysed_managers: 30 },
        { league_id: 7, name: "Pils, betting og poeng", managers: 3, rank: 3, last_rank: 3, analysed_managers: 3 },
      ] });
    }
    if (url.includes("/rival/")) {
      return json({ event: 6, team_id: 4242, rival_id: 1, only_you: [{ player_id: 4, name: "Mine", team_short: "MCI", position: "FWD", role: "CAPTAIN", next_gw_points: 6.5 }],
        only_rival: [{ player_id: 2, name: "Saka", team_short: "ARS", position: "MID", role: "CAPTAIN", next_gw_points: 5.1 }], shared: [], same_captain: false,
        unique_next_gw_points: { you: 6.5, rival: 5.1 }, basis: "Both squads as picked for GW6." });
    }
    if (url.includes("/api/v1/league/7")) {
      return json({ league_id: 7, name: "Pils, betting og poeng", event: 6, managers: 3, analysed_managers: 3, max_analysed_managers: 30,
        standings: [
          { team_id: 1, team_name: "No Salad", manager: "Enger", rank: 1, last_rank: 1, event_points: 60, total: 417, gap_to_you: 145, active_chip: "wildcard", is_you: false },
          { team_id: 2, team_name: "Ballerotellitubby", manager: "Mathisen", rank: 2, last_rank: 2, event_points: 44, total: 400, gap_to_you: 128, active_chip: null, is_you: false },
          { team_id: 4242, team_name: "laget mitt", manager: "Witzøe", rank: 3, last_rank: 3, event_points: 29, total: 272, gap_to_you: 0, active_chip: null, is_you: true },
        ],
        players: [player(2, "Saka", { owners: 2, captains: 2, eo: 133.3, rival_eo: 200, role: "THREAT" }), player(4, "Mine", { you: "CAPTAIN", rival_eo: 0, role: "DIFFERENTIAL" })],
        thresholds: { threat_eo: 50, differential_eo: 25 }, basis: "Squads from GW6, the latest deadline that has passed." });
    }
    return route(input, init);
  });
}

test("the smallest league opens with gaps, threats and a head-to-head", async () => {
  serve(mockApi());
  render(<TeamProvider><LeagueWorkspace /></TeamProvider>);
  expect(await screen.findByRole("heading", { name: "Pils, betting og poeng" })).toBeInTheDocument();
  // Gap to the leader and to the next place above.
  expect(screen.getByText("145 pts")).toBeInTheDocument();
  expect(screen.getByText("128 pts")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Threats" }));
  expect(screen.getByText("Saka")).toBeInTheDocument();
  expect(screen.queryByText("Mine")).not.toBeInTheDocument();
  const leader = screen.getByText("No Salad").closest("tr")!;
  await userEvent.click(within(leader).getByRole("button", { name: "Compare" }));
  expect(await screen.findByText(/Unique starters project 6.5 xP for you and 5.1 xP for No Salad/)).toBeInTheDocument();
  expect(screen.getByText(/Your captains differ/)).toBeInTheDocument();
});
