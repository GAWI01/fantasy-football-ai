import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { TeamProvider, useTeam } from "@/app/providers/TeamProvider";
import { makeDashboard } from "@/test-utils/fixtures";
import { mockApi } from "@/test-utils/mockApi";
import { PlanWorkspace } from "./PlanWorkspace";
import { Overview } from "@/components/overview/Overview";

beforeEach(() => localStorage.setItem("fpl-ai-team-id", "4242"));
// Tabs keep the open section in the address; start every test on Transfers.
afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); window.history.replaceState(null, "", "/"); });

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

test("a hold plan explains the conservative policy without threshold claims", async () => {
  serveDashboard(mockApi(), makeDashboard({ verdict: "HOLD" }));
  const { container } = render(<TeamProvider><PlanWorkspace /></TeamProvider>);
  expect(await screen.findByText(/The planner recommends holding under its conservative policy/)).toBeInTheDocument();
  expect(screen.getByText(/Evaluated move · conservative policy recommends holding/)).toBeInTheDocument();
  expect(container.textContent).not.toMatch(/threshold/i);
});

test("the explanation describes the hit and holding policy the engine actually applies", async () => {
  serveDashboard(mockApi(), makeDashboard());
  const { container } = render(<TeamProvider><PlanWorkspace /></TeamProvider>);
  await screen.findByRole("heading", { name: /Ekström → Castellano/ });
  await userEvent.click(screen.getByRole("tab", { name: "Why" }));
  expect(container.textContent).toMatch(/takes a hit only when the weighted horizon gain beats the hit plus a safety margin/);
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
  await userEvent.click(await screen.findByRole("tab", { name: "Chips" }));

  expect(await screen.findByText(/GW9: 4 of your starters/)).toBeInTheDocument();
  expect(screen.getByText("Best: GW9")).toBeInTheDocument();
  expect(screen.getByText(/This week 6.0 · worth it from 12.0/)).toBeInTheDocument();
  expect(screen.getByText("Used this half: Wildcard.")).toBeInTheDocument();
});

test("projected point metrics stay distinct from weighted scores and conservative overrides", async () => {
  const dashboard = makeDashboard();
  const strategy = dashboard.data.decision!.intelligence!.transfer_strategy;
  Object.assign(strategy, { projected_gain: 13, projected_net_gain: 13, horizon_gain: 9.4, net_gain: 9.4, decision_score: 6.5 });
  Object.assign(strategy.alternatives[0], { projected_gain: 22, projected_net_gain: 18, horizon_gain: 15, net_gain: 11, decision_score: 8.5 });
  serveDashboard(mockApi(), dashboard);
  render(<TeamProvider><PlanWorkspace /></TeamProvider>);
  await screen.findByRole("heading", { name: /Ekström → Castellano/ });
  const rows = within(screen.getByRole("radiogroup", { name: "Transfer scenarios" })).getAllByRole("radio");
  expect(rows[0]).not.toHaveTextContent("Recommended");
  expect(rows[1]).toHaveTextContent("Recommended");
  expect(screen.getByText(/conservative.*may recommend.*lower single-stage score/i)).toBeInTheDocument();
  expect(screen.getByText("5-GW projected gain").closest("div")).toHaveTextContent("+13.0 xP");
  expect(screen.getByText("5-GW net after hits").closest("div")).toHaveTextContent("+13.0 xP");
  expect(rows[1]).toHaveTextContent("+9.4 weighted gain");
  expect(rows[1]).toHaveTextContent("+6.5");
});

test("older forecasts never turn weighted values into projected FPL point metrics", async () => {
  serveDashboard(mockApi(), makeDashboard());
  render(<TeamProvider><PlanWorkspace /></TeamProvider>);
  await screen.findByRole("heading", { name: /Ekström → Castellano/ });
  expect(screen.getByText("5-GW projected gain").closest("div")).toHaveTextContent("Unavailable");
  expect(screen.getByText("5-GW net after hits").closest("div")).toHaveTextContent("Unavailable");
});

test("the plan opens on Transfers and an old #chips link opens the Chips section", async () => {
  serveDashboard(mockApi(), makeDashboard());
  window.history.replaceState(null, "", "#chips");
  render(<TeamProvider><PlanWorkspace /></TeamProvider>);
  expect(await screen.findByRole("tab", { name: /Chips/ })).toHaveAttribute("aria-selected", "true");
  await userEvent.click(screen.getByRole("tab", { name: "Transfers" }));
  expect(window.location.hash).toBe("#transfers");
  expect(screen.getByRole("heading", { name: "Compare options" })).toBeInTheDocument();
  window.history.replaceState(null, "", "#");
});
