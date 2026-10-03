import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { TeamProvider } from "@/app/providers/TeamProvider";
import { expectNoA11yViolations } from "@/test-utils/accessibility";
import { mockApi } from "@/test-utils/mockApi";
import { TeamWorkspace } from "./TeamWorkspace";

beforeEach(() => localStorage.setItem("fpl-ai-team-id", "4242"));
afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

const player = (name: string) => screen.getByRole("button", { name: new RegExp(`^${name},`) });

test("shows all fifteen players including both goalkeepers", async () => {
  mockApi();
  const { container } = render(<TeamProvider><TeamWorkspace /></TeamProvider>);
  await screen.findByRole("heading", { name: "My Team" });
  const pitch = screen.getByRole("group", { name: /Starting eleven/ });
  expect(within(pitch).getAllByRole("button")).toHaveLength(11);
  expect(player("Okafor")).toHaveAccessibleName(/GKP/);
  expect(player("Pryce")).toHaveAccessibleName(/bench 1/);
  await expectNoA11yViolations(container);
});

test("tap-to-swap makes a legal substitution and marks the lineup as a simulation", async () => {
  mockApi();
  render(<TeamProvider><TeamWorkspace /></TeamProvider>);
  await screen.findByRole("heading", { name: "My Team" });
  await userEvent.click(player("Varga"));
  expect(screen.getByRole("region", { name: "Actions for Varga" })).toBeInTheDocument();
  await userEvent.click(player("Moreau"));
  expect(screen.getByText(/Moreau in for Varga · 4-4-2/, { selector: ".toast" })).toBeInTheDocument();
  expect(screen.getByText("Simulation. Not saved to FPL.")).toBeInTheDocument();
  const pitch = screen.getByRole("group", { name: /Starting eleven/ });
  expect(within(pitch).getByRole("button", { name: /^Moreau,/ })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Reset/ }));
  expect(within(screen.getByRole("group", { name: /Starting eleven/ })).getByRole("button", { name: /^Varga,/ })).toBeInTheDocument();
});

test("illegal swaps are not offered: the goalkeeper only swaps with the other goalkeeper", async () => {
  mockApi();
  render(<TeamProvider><TeamWorkspace /></TeamProvider>);
  await screen.findByRole("heading", { name: "My Team" });
  await userEvent.click(player("Okafor"));
  expect(player("Pryce")).toHaveClass("is-target");
  expect(player("Moreau")).toHaveClass("is-dimmed");
  await userEvent.click(player("Moreau"));
  expect(player("Okafor")).toHaveAttribute("aria-pressed", "false");
  expect(player("Moreau")).toHaveAttribute("aria-pressed", "true");
});
