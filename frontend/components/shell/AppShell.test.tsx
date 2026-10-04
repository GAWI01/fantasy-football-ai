import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { TeamProvider } from "@/app/providers/TeamProvider";
import { useResource } from "@/lib/hooks/useResource";
import { makeDashboard } from "@/test-utils/fixtures";
import { expectNoA11yViolations } from "@/test-utils/accessibility";
import { mockApi } from "@/test-utils/mockApi";
import { AppShell } from "./AppShell";

vi.mock("next/navigation", () => ({ usePathname: () => "/players" }));

beforeEach(() => localStorage.clear());
afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

test("desktop navigation lists every destination and marks the current page", async () => {
  const { container } = render(<TeamProvider><AppShell><p>Page</p></AppShell></TeamProvider>);
  const nav = screen.getByRole("navigation", { name: "Primary" });
  for (const label of ["Overview", "My Team", "Plan & Transfers", "Players", "Fixtures", "History & Review", "Settings"]) {
    expect(within(nav).getByRole("link", { name: new RegExp(label) })).toBeInTheDocument();
  }
  expect(within(nav).getByRole("link", { name: /Players/ })).toHaveAttribute("aria-current", "page");
  await expectNoA11yViolations(container);
});

test("the phone tab bar opens a More sheet with the remaining destinations", async () => {
  render(<TeamProvider><AppShell><p>Page</p></AppShell></TeamProvider>);
  const tabs = screen.getByRole("navigation", { name: "Mobile primary" });
  expect(within(tabs).getAllByRole("link")).toHaveLength(4);
  await userEvent.click(within(tabs).getByRole("button", { name: "More" }));
  const more = await screen.findByRole("navigation", { name: "More destinations" });
  expect(within(more).getByRole("link", { name: "Fixtures" })).toBeInTheDocument();
  expect(within(more).getByRole("link", { name: "Settings" })).toBeInTheDocument();
});

test("shows a stale-data banner when official data is cached", async () => {
  localStorage.setItem("fpl-ai-team-id", "4242");
  mockApi({ stale: true });
  render(<TeamProvider><AppShell><p>Page</p></AppShell></TeamProvider>);
  expect(await screen.findByText(/last cached data/)).toBeInTheDocument();
});

test("freshness reflects the official fetch time rather than envelope generation", async () => {
  localStorage.setItem("fpl-ai-team-id", "4242");
  vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-10-03T09:05:00Z"));
  const dashboard = makeDashboard();
  dashboard.meta.generated_at = "2026-10-03T09:05:00Z";
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify(dashboard), { status: 200 }));
  render(<TeamProvider><AppShell><p>Page</p></AppShell></TeamProvider>);
  expect(await screen.findByText("Updated 5 min ago")).toBeInTheDocument();
});

test("the shell refresh updates mounted page resources as well as the dashboard", async () => {
  localStorage.setItem("fpl-ai-team-id", "4242");
  mockApi();
  const fetcher = vi.fn().mockResolvedValueOnce("Old market").mockResolvedValue("New market");
  function MarketProbe() {
    const resource = useResource<string>("market-probe", fetcher);
    return <p>{resource.data}</p>;
  }
  render(<TeamProvider><AppShell><MarketProbe /></AppShell></TeamProvider>);
  await screen.findByText("Old market");
  await userEvent.click(await screen.findByRole("button", { name: "Refresh data" }));
  expect(await screen.findByText("New market")).toBeInTheDocument();
});

test("unverified model forecasts carry a visible evaluation label", async () => {
  localStorage.setItem("fpl-ai-team-id", "4242");
  const dashboard = makeDashboard();
  Object.assign(dashboard.meta, { model_validation_state: "unverified" });
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify(dashboard), { status: 200 }));
  render(<TeamProvider><AppShell><p>Page</p></AppShell></TeamProvider>);
  expect(await screen.findByText(/Unverified model forecasts/)).toBeInTheDocument();
});
