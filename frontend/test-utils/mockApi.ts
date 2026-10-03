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
    if (url.pathname.startsWith("/api/v1/review/")) return json(makeReview(Number(url.searchParams.get("event") ?? 6)));
    return json({ detail: "Not found" }, 404);
  });
}
