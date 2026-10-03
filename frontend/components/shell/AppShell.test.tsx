import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { TeamProvider } from "@/app/providers/TeamProvider";
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
