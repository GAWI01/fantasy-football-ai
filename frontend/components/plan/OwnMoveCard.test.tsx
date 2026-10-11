import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { TeamProvider } from "@/app/providers/TeamProvider";
import { makeDashboard } from "@/test-utils/fixtures";
import { mockApi } from "@/test-utils/mockApi";
import { PlanWorkspace } from "./PlanWorkspace";
import { ownMoveVerdict } from "./OwnMoveCard";

beforeEach(() => localStorage.setItem("fpl-ai-team-id", "4242"));
afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

const recommended = { transfers: [{ player_out_id: 109, player_out: "Ekström", player_in_id: 201, player_in: "Castellano" }], decision_score: 7.4 };

test("the verdict compares the manager's move with holding and the recommendation", () => {
  const option = { transfers: [], horizon_gain: 0, coverage: 1 };
  expect(ownMoveVerdict({ legal: true, option: { ...option, decision_score: -1.2 }, recommended, free_transfers: 1 })).toMatch(/Worse than holding by 1.2 points: .* The recommended plan scores \+7.4/);
  expect(ownMoveVerdict({ legal: true, option: { ...option, decision_score: 3.0 }, recommended, free_transfers: 1 })).toMatch(/4.4 below the recommended plan/);
  expect(ownMoveVerdict({ legal: true, option: { ...option, decision_score: 7.4 }, recommended, free_transfers: 1 })).toMatch(/As good as the recommended plan/);
  expect(ownMoveVerdict({ legal: false, reason: "This move is not allowed: over budget.", recommended, free_transfers: 1 })).toMatch(/over budget/);
});

test("a manager can score their own transfer from the plan page", async () => {
  const fetchSpy = mockApi();
  const route = fetchSpy.getMockImplementation()!;
  const evaluated: string[] = [];
  fetchSpy.mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.includes("/evaluate/")) {
      evaluated.push(url);
      return new Response(JSON.stringify({
        data: { legal: true, option: { transfers: [], next_gw_gain: 0.8, horizon_gain: 3.1, gross_gain: 3.1, hit_cost: 0, decision_score: 1.1, coverage: 1 }, recommended, free_transfers: 1 },
        meta: { source: "model", fetched_at: "2026-10-03T09:00:00Z", stale: false, version: "v" }, errors: [],
      }), { status: 200 });
    }
    if (url.includes("/dashboard/")) return new Response(JSON.stringify(makeDashboard()), { status: 200 });
    return route(input, init);
  });
  render(<TeamProvider><PlanWorkspace /></TeamProvider>);
  const sell = await screen.findByRole("combobox", { name: /Sell/ });
  await userEvent.selectOptions(sell, "109");
  const buy = screen.getByRole("combobox", { name: /Buy/ });
  const firstCandidate = (buy as HTMLSelectElement).options[1].value;
  await userEvent.selectOptions(buy, firstCandidate);
  await userEvent.click(screen.getByRole("button", { name: "Score this move" }));
  expect(await screen.findByText(/Better than holding by 1.1, but 6.3 below the recommended plan/)).toBeInTheDocument();
  expect(evaluated[0]).toContain(`sell=109&buy=${firstCandidate}`);
});
