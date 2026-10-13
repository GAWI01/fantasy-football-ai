import { vi } from "vitest";

import { clearResourceCache } from "@/lib/hooks/useResource";
import { makeDashboard, makeFixtureMatrix, makePlayerMarket, makeReview, type DashboardOptions } from "./fixtures";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

/** Routes fetch calls to the fictional fixtures. Returns the spy. */
export function mockApi(options: DashboardOptions & { dashboardStatus?: number; detail?: string } = {}) {
  clearResourceCache();
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = new URL(String(input instanceof Request ? input.url : input), "http://localhost");
    if (url.pathname.startsWith("/api/v1/dashboard/")) {
      if (options.dashboardStatus && options.dashboardStatus >= 400) return json({ detail: options.detail ?? "Upstream failed" }, options.dashboardStatus);
      return json(makeDashboard(options));
    }
    if (url.pathname === "/api/v1/players") return json(makePlayerMarket());
    if (url.pathname === "/api/v1/fixture-matrix") return json(makeFixtureMatrix(Number(url.searchParams.get("horizon") ?? 5)));
    if (url.pathname.startsWith("/api/v1/leagues/")) {
      return json({ data: { team_id: 4242, leagues: [{ league_id: 77, name: "Office league", managers: 7, rank: 4, last_rank: 5, analysed_managers: 7 }] }, meta: { source: "official", fetched_at: "2026-10-03T09:00:00Z", stale: false }, errors: [] });
    }
    if (/^\/api\/v1\/league\/\d+\/captain$/.test(url.pathname)) {
      const candidate = (player_id: number, name: string, expected: number, share: number, kind: string, low: number, high: number) => ({
        player_id, name, expected, range: { low, high, median: expected, haul_chance: 0.16, blank_chance: 0.13 }, rival_captain_share: share, rival_eo: share * 2, kind, swing_high: high * (2 - share * 2), swing_low: low,
      });
      return json({
        data: {
          league_id: 77, league_name: "Office league", rivals: 6, gap_to_leader: 40, gameweeks_left: 31,
          mode: { mode: "balanced", text: "You are 40 points behind with 31 Gameweeks left: plenty of time, so expected points come first." },
          candidates: [candidate(31, "Duarte", 6.9, 0.67, "safe", 2, 10), candidate(32, "Castellano", 5.6, 0, "differential", 2, 9)],
          best_id: 31, safe_id: 31, differential_id: 32,
          pick: { player_id: 31, name: "Duarte", reason: "the highest expected points", cost: 0 },
          basis: "Squads from GW6, the latest deadline that has passed.",
        },
        meta: { source: "official", fetched_at: "2026-10-03T09:00:00Z", stale: false },
        errors: [],
      });
    }
    if (url.pathname.startsWith("/api/v1/price-swaps/")) {
      return json({
        data: {
          swaps: [{ player_out_id: 11, player_out: "Varga", player_in_id: 901, player_in: "Brennan", position: "MID", sell_price: 6.1, buy_price: 7.8,
            out_likelihood: -4, in_likelihood: 5, next_gw_gain: 0.8, projected_gain: 1.9, projected_net_gain: 1.9, hit_cost: 0, decision_score: -0.6 }],
          owned_fallers: [{ player_id: 11, name: "Varga", likelihood: -4 }],
          risers_considered: 3, pairs_evaluated: 12, point_floor: -0.5, free_transfers: 1, selling_prices_known: true, horizon: 5,
        },
        meta: { source: "model", fetched_at: "2026-10-03T09:00:00Z", stale: false },
        errors: [],
      });
    }
    if (url.pathname.startsWith("/api/v1/review/")) return json(makeReview(Number(url.searchParams.get("event") ?? 6)));
    return json({ detail: "Not found" }, 404);
  });
}
