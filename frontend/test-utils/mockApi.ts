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
