import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { TeamProvider } from "@/app/providers/TeamProvider";
import { expectNoA11yViolations } from "@/test-utils/accessibility";
import { mockApi } from "@/test-utils/mockApi";
import { Overview } from "./Overview";

beforeEach(() => localStorage.setItem("fpl-ai-team-id", "4242"));
afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

const renderOverview = () => render(<TeamProvider><Overview /></TeamProvider>);

test("decision mode leads with the transfer, captain, risk and a recommendation-only disclaimer", async () => {
  mockApi({ phase: "decision", verdict: "TRANSFER" });
  const { container } = renderOverview();
  const plan = await screen.findByRole("region", { name: /Gameweek 7 plan/ });
  expect(within(plan).getByText("Make the move")).toBeInTheDocument();
  expect(await within(plan).findAllByText("Castellano")).not.toHaveLength(0);
  expect(within(plan).getAllByText("Ekström").length).toBeGreaterThan(0);
  expect(within(plan).getByText("Duarte")).toBeInTheDocument();
  expect(within(plan).getByText(/Varga · starter at risk/)).toBeInTheDocument();
  expect(within(plan).getByText(/Recommendation only/)).toBeInTheDocument();
  expect(within(plan).queryByText(/Read-only/)).not.toBeInTheDocument();
  await expectNoA11yViolations(container);
});

test("hold verdict shows the rejected move as context, not as the call", async () => {
  mockApi({ phase: "decision", verdict: "HOLD" });
  renderOverview();
  const plan = await screen.findByRole("region", { name: /Gameweek 7 plan/ });
  expect(within(plan).getByText("Hold")).toBeInTheDocument();
  expect(within(plan).getByText("Best move found, not recommended")).toBeInTheDocument();
  expect(within(plan).queryByText("Make the move")).not.toBeInTheDocument();
});

test("live mode shows live points and never offers the passed-deadline plan as an action", async () => {
  mockApi({ phase: "live" });
  const { container } = renderOverview();
  expect(await screen.findByRole("heading", { name: "Live points" })).toBeInTheDocument();
  expect(screen.queryByText("Make the move")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /GW7 plan/ })).not.toBeInTheDocument();
  expect(screen.getByText("Your matches")).toBeInTheDocument();
  await expectNoA11yViolations(container);
});

test("after the deadline with no live games the plan is marked read-only", async () => {
  mockApi({ phase: "settled" });
  renderOverview();
  expect(await screen.findByText("Read-only · deadline passed")).toBeInTheDocument();
  expect(screen.getByText("This plan is past its deadline")).toBeInTheDocument();
});

test("missing model output is reported instead of inventing a plan", async () => {
  mockApi({ noDecision: true });
  renderOverview();
  expect(await screen.findByText("No model plan right now")).toBeInTheDocument();
  expect(screen.queryByText("Make the move")).not.toBeInTheDocument();
});

test("a failed load shows the API error with recovery actions", async () => {
  mockApi({ dashboardStatus: 503, detail: "FPL is temporarily unavailable" });
  renderOverview();
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Your team could not be loaded");
  expect(alert).toHaveTextContent("FPL is temporarily unavailable");
  expect(screen.getByRole("button", { name: "Use another Team ID" })).toBeInTheDocument();
});

test("connects from a pasted team URL", async () => {
  localStorage.clear();
  const fetch = mockApi();
  renderOverview();
  await userEvent.type(await screen.findByLabelText("Your FPL Team ID"), "https://fantasy.example/entry/4242/event/6");
  await userEvent.click(screen.getByRole("button", { name: /Open my cockpit/ }));
  expect(await screen.findByRole("heading", { name: "Midnight Pressers" })).toBeInTheDocument();
  expect(fetch.mock.calls.some(([input]) => String(input).includes("/api/v1/dashboard/4242"))).toBe(true);
});

test("the example team opens gawi's cockpit in one click", async () => {
  localStorage.clear();
  const fetch = mockApi();
  renderOverview();
  await userEvent.click(await screen.findByRole("button", { name: /Try gawi’s team 665875/ }));
  expect(fetch.mock.calls.some(([input]) => String(input).includes("/api/v1/dashboard/665875"))).toBe(true);
});
