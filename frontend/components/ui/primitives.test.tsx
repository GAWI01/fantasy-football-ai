import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Card, SourceBadge, SourceScope } from "./primitives";


test("a card labels each source once: inner badges for a header source are left out", () => {
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
