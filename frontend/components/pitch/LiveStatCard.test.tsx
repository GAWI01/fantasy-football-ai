import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PitchPlayer } from "@/components/pitch/Pitch";
import { buildSquad } from "@/lib/model/squad";
import { makeDashboard } from "@/test-utils/fixtures";

function livePlayer() {
  const data = makeDashboard({ phase: "live" }).data;
  const first = data.live!.picks[0];
  first.event_points = 4;
  first.breakdown = [
    { stat: "minutes", value: 90, points: 2 },
    { stat: "saves", value: 4, points: 1 },
    { stat: "bonus", value: 1, points: 1, provisional: true },
  ];
  return buildSquad(data).find((player) => player.id === first.player_id)!;
}

describe("live stats card", () => {
  it("opens on tap with the official points breakdown and closes with Escape", () => {
    const player = livePlayer();
    render(<PitchPlayer player={player} mode="live" />);
    const tile = screen.getByRole("button", { name: new RegExp(player.name) });

    fireEvent.click(tile);

    const card = screen.getByRole("tooltip");
    expect(tile).toHaveAttribute("aria-expanded", "true");
    expect(card).toHaveTextContent("Minutes played");
    expect(card).toHaveTextContent("Saves");
    expect(card).toHaveTextContent("+1");
    expect(card).toHaveTextContent("Bonus not confirmed yet");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("falls back to the raw live stats when the points breakdown is missing", () => {
    const data = makeDashboard({ phase: "live" }).data;
    const first = data.live!.picks[0];
    Object.assign(first, { event_points: 6, live_minutes: 90, saves: 4, bonus: 2, breakdown: undefined });
    const player = buildSquad(data).find((item) => item.id === first.player_id)!;
    render(<PitchPlayer player={player} mode="live" />);

    fireEvent.click(screen.getByRole("button", { name: new RegExp(player.name) }));

    const card = screen.getByRole("tooltip");
    expect(card).toHaveTextContent("Minutes played");
    expect(card).toHaveTextContent("Saves");
    expect(card).toHaveTextContent("+2");
    expect(card).not.toHaveTextContent("No points recorded yet");
  });

  it("does not turn editable tiles into stat buttons", () => {
    const player = livePlayer();
    render(<PitchPlayer player={player} mode="projected" />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
