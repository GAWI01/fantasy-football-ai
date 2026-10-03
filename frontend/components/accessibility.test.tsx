import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, test, vi } from "vitest";

import { TeamProvider } from "@/app/providers/TeamProvider";
import { expectNoA11yViolations } from "@/test-utils/accessibility";
import { mockApi } from "@/test-utils/mockApi";
import { FixturesWorkspace } from "./fixtures/FixturesWorkspace";
import { PlanWorkspace } from "./plan/PlanWorkspace";
import { PlayersWorkspace } from "./players/PlayersWorkspace";
import { ReviewWorkspace } from "./review/ReviewWorkspace";
import { SettingsWorkspace } from "./settings/SettingsWorkspace";

beforeEach(() => localStorage.setItem("fpl-ai-team-id", "4242"));
afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

const inProvider = (node: React.ReactNode) => render(<TeamProvider>{node}</TeamProvider>);

test("plan workspace has no automated WCAG A/AA violations", async () => {
  mockApi();
  const { container } = inProvider(<PlanWorkspace />);
  await screen.findByRole("heading", { name: "Compare options" });
  await expectNoA11yViolations(container);
});

test("players workspace has no automated WCAG A/AA violations", async () => {
  mockApi();
  const { container } = inProvider(<PlayersWorkspace />);
  await screen.findByRole("button", { name: "Open Castellano details" });
  await expectNoA11yViolations(container);
});

test("fixtures workspace has no automated WCAG A/AA violations", async () => {
  mockApi();
  const { container } = inProvider(<FixturesWorkspace />);
  await screen.findByRole("rowheader", { name: /Arsenal/ });
  await expectNoA11yViolations(container);
});

test("review workspace has no automated WCAG A/AA violations", async () => {
  mockApi();
  const { container } = inProvider(<ReviewWorkspace />);
  await screen.findByText("GW6 against the model");
  await expectNoA11yViolations(container);
});

test("settings has no automated WCAG A/AA violations", async () => {
  mockApi();
  const { container } = inProvider(<SettingsWorkspace />);
  await screen.findByText("Midnight Pressers");
  await expectNoA11yViolations(container);
});
