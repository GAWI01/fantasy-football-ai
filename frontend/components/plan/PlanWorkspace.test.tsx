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
