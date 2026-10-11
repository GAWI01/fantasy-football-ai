import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { TeamProvider, useTeam } from "@/app/providers/TeamProvider";
import { makeDashboard } from "@/test-utils/fixtures";
import { mockApi } from "@/test-utils/mockApi";
import { PlanWorkspace } from "./PlanWorkspace";
import { Overview } from "@/components/overview/Overview";

beforeEach(() => localStorage.setItem("fpl-ai-team-id", "4242"));
afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

test("a failed refresh is visible while the last plan stays available", async () => {
  const fetchSpy = mockApi();
  function Refresh() {
    const { refresh } = useTeam();
    return <button onClick={() => void refresh()}>Refresh test data</button>;
  }
  render(<TeamProvider><Refresh /><PlanWorkspace /></TeamProvider>);
  await screen.findByRole("heading", { name: /Ekström → Castellano/ });
  fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Official service unavailable" }), { status: 502 }));
  await userEvent.click(screen.getByRole("button", { name: "Refresh test data" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Official service unavailable");
  expect(screen.getByRole("heading", { name: /Ekström → Castellano/ })).toBeInTheDocument();
});

test("estimated selling proceeds are labelled before a transfer recommendation", async () => {
  const fetchSpy = mockApi();
  const route = fetchSpy.getMockImplementation()!;
  fetchSpy.mockImplementation(async (input, init) => {
    if (String(input).includes("/dashboard/")) {
      const dashboard = makeDashboard();
      Object.assign(dashboard.data.decision!.transfers!, { budget_is_estimate: true });
      return new Response(JSON.stringify(dashboard), { status: 200 });
    }
    return route(input, init);
  });
  render(<TeamProvider><PlanWorkspace /></TeamProvider>);
  expect((await screen.findAllByText(/Affordability is estimated/))[0]).toBeInTheDocument();
});

test("estimated chip squad affordability remains labelled on Overview", async () => {
  const fetchSpy = mockApi();
  const route = fetchSpy.getMockImplementation()!;
  fetchSpy.mockImplementation(async (input, init) => {
    if (String(input).includes("/dashboard/")) {
      const dashboard = makeDashboard();
      dashboard.data.decision!.intelligence!.chip_scenarios = { budget_is_estimate: true };
      return new Response(JSON.stringify(dashboard), { status: 200 });
    }
    return route(input, init);
  });
  render(<TeamProvider><Overview /></TeamProvider>);
  expect(await screen.findByText("Squad affordability estimated from market prices.")).toBeInTheDocument();
});

function serveDashboard(fetchSpy: ReturnType<typeof mockApi>, dashboard: ReturnType<typeof makeDashboard>) {
  const route = fetchSpy.getMockImplementation()!;
  fetchSpy.mockImplementation(async (input, init) => {
    if (String(input).includes("/dashboard/")) return new Response(JSON.stringify(dashboard), { status: 200 });
    return route(input, init);
  });
}

test("a hold plan explains the rejected move against the value of rolling, without threshold claims", async () => {
  serveDashboard(mockApi(), makeDashboard({ verdict: "HOLD" }));
  const { container } = render(<TeamProvider><PlanWorkspace /></TeamProvider>);
  expect(await screen.findByText(/No move beats the value of rolling the free transfer/)).toBeInTheDocument();
  expect(screen.getByText(/rolling is worth more/)).toBeInTheDocument();
  expect(container.textContent).not.toMatch(/threshold/i);
});

test("the explanation describes the hit and holding policy the engine actually applies", async () => {
  serveDashboard(mockApi(), makeDashboard());
  const { container } = render(<TeamProvider><PlanWorkspace /></TeamProvider>);
  await screen.findByRole("heading", { name: /Ekström → Castellano/ });
  expect(container.textContent).toMatch(/takes a hit only when the five-Gameweek gain beats the hit plus a safety margin/);
  expect(container.textContent).toMatch(/Holding is always an option/);
  expect(container.textContent).not.toMatch(/clears its threshold/);
});

test("a provisional forecast is labelled while the previous Gameweek is played", async () => {
  const dashboard = makeDashboard();
  Object.assign(dashboard.meta, { forecast_stage: "provisional", history_cutoff_gw: 5 });
  serveDashboard(mockApi(), dashboard);
  render(<TeamProvider><PlanWorkspace /></TeamProvider>);
  const pill = await screen.findByText("Provisional forecast");
  expect(pill).toHaveAttribute("title", expect.stringContaining("results up to GW5"));
});

test("each remaining chip says whether to play it and which week suits it", async () => {
  const fetchSpy = mockApi();
  const dashboard = makeDashboard();
  dashboard.data.decision!.intelligence!.chip_outlook = [
    { chip: "WILDCARD", label: "Wildcard", available: false, verdict: null, this_week: null, threshold: null, best_window: null, summary: null },
    { chip: "FREE_HIT", label: "Free Hit", available: true, verdict: "SAVE", this_week: null, threshold: 8, best_window: { gameweek: 9, value: 4, unit: "starters missing" }, summary: "GW9: 4 of your starters have no match or are ruled out. That is a Free Hit week." },
    { chip: "BENCH_BOOST", label: "Bench Boost", available: true, verdict: "SAVE", this_week: 6, threshold: 12, best_window: { gameweek: 10, value: 13, unit: "bench xP" }, summary: "Best week in view: GW10." },
  ];
  serveDashboard(fetchSpy, dashboard);
  render(<TeamProvider><PlanWorkspace /></TeamProvider>);

  expect(await screen.findByText(/GW9: 4 of your starters/)).toBeInTheDocument();
  expect(screen.getByText("Best: GW9")).toBeInTheDocument();
  expect(screen.getByText(/This week 6.0 · worth it from 12.0/)).toBeInTheDocument();
  expect(screen.getByText("Used this half: Wildcard.")).toBeInTheDocument();
});
