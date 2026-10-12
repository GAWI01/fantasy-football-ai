import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { DATA_LABELS_KEY } from "@/lib/preferences";
import { resetSectionSignals, SECTIONS_KEY } from "@/lib/sections";

import { Card, SourceBadge, SourceScope } from "./primitives";


test("with data labels off only Live and Cached show", () => {
  localStorage.clear();
  render(
    <Card title="Prices" source="official">
      <p>Price <SourceBadge kind="model" /></p>
      <SourceBadge kind="live" />
      <SourceBadge kind="cached" />
      <SourceBadge kind="derived" always />
    </Card>,
  );

  expect(screen.queryByText("FPL data")).not.toBeInTheDocument();
  expect(screen.queryByText("Model")).not.toBeInTheDocument();
  expect(screen.getByText("Live")).toBeInTheDocument();
  expect(screen.getByText("Cached")).toBeInTheDocument();
  expect(screen.getByText("Derived")).toBeInTheDocument();
});


test("a card labels each source once: inner badges for a header source are left out", () => {
  localStorage.setItem(DATA_LABELS_KEY, "on");
  render(
    <Card title="Transfer decision" source={["model", "derived"]}>
      <p>Next GW <SourceBadge kind="derived" /></p>
      <p>5-GW gain <SourceBadge kind="model" /></p>
      <p>Price <SourceBadge kind="official" /></p>
    </Card>,
  );

  expect(screen.getAllByText("Model")).toHaveLength(1);
  expect(screen.getAllByText("Derived")).toHaveLength(1);
  // A number from a source the header does not name keeps its own label.
  expect(screen.getByText("FPL data")).toBeInTheDocument();
});


test("pinned badges always show, and a custom label is never dropped", () => {
  localStorage.setItem(DATA_LABELS_KEY, "on");
  render(
    <SourceScope kinds={["official"]}>
      <SourceBadge kind="official" pinned />
      <SourceBadge kind="official" />
      <SourceBadge kind="official" label="FPL data · GW6" />
    </SourceScope>,
  );

  expect(screen.getAllByText("FPL data")).toHaveLength(1);
  expect(screen.getByText("FPL data · GW6")).toBeInTheDocument();
});


test("a collapsible card opens and closes from its header and remembers the choice", async () => {
  localStorage.clear();
  resetSectionSignals();
  const user = userEvent.setup();
  const { unmount } = render(
    <Card title="Season" collapse={{ id: "season", summary: "Overall rank 8.7M", defaults: { mobile: false, desktop: true } }}>
      <p>Rank chart</p>
    </Card>,
  );
  const toggle = screen.getByRole("button", { name: "Season" });
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(screen.queryByText("Overall rank 8.7M")).not.toBeInTheDocument();

  await user.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByText("Overall rank 8.7M")).toBeInTheDocument();
  // Closed content stays in the page but cannot be reached.
  expect(screen.getByText("Rank chart").closest(".card-body")).toHaveAttribute("inert");
  expect(JSON.parse(localStorage.getItem(SECTIONS_KEY) ?? "{}")).toMatchObject({ v: 1, desktop: { season: false } });

  unmount();
  render(<Card title="Season" collapse={{ id: "season", defaults: { mobile: false, desktop: true } }}><p>Rank chart</p></Card>);
  expect(screen.getByRole("button", { name: "Season" })).toHaveAttribute("aria-expanded", "false");
});


test("something new opens a closed section until the reader closes it", async () => {
  localStorage.clear();
  resetSectionSignals();
  const user = userEvent.setup();
  const card = (signal: string | null) => (
    <Card title="Chip" collapse={{ id: "chip", defaults: { mobile: false, desktop: false }, signal }}><p>Play Free Hit</p></Card>
  );
  const { rerender } = render(card("chip:7:freehit"));
  const toggle = screen.getByRole("button", { name: "Chip" });
  expect(toggle).toHaveAttribute("aria-expanded", "true");

  await user.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  // The next live refresh carries the same signal: it stays closed.
  rerender(card("chip:7:freehit"));
  expect(screen.getByRole("button", { name: "Chip" })).toHaveAttribute("aria-expanded", "false");
  // A different signal is new again.
  rerender(card("chip:8:bboost"));
  expect(screen.getByRole("button", { name: "Chip" })).toHaveAttribute("aria-expanded", "true");
});
