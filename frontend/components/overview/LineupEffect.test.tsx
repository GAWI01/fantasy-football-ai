import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { LineupEffect, MoveRow } from "@/components/overview/GameweekPlanCard";
import type { GameweekPlan, ScenarioView, TransferMove } from "@/lib/model/plan";

const player = (id: number, name: string) => ({ id, name }) as GameweekPlan["modelXI"][number];
const move = { outId: 15, outName: "Benchy", inId: 20, inName: "Newcomer", inPrice: 6, position: "DEF",
  out: null, incoming: null, inTeam: null, inTeamShort: null, outXp: 2, inXp: 4.4 } as TransferMove;
const scenario = { moves: [move], nextGwGain: 2.3 } as ScenarioView;
const starters = Array.from({ length: 11 }, (_, index) => player(index + 1, `Starter ${index + 1}`));
const plan = {
  lineupAfterTransfers: true,
  owned: { xi: starters, bench: [player(12, "Sub A"), player(13, "Sub B"), player(14, "Sub C"), player(15, "Benchy")] },
  modelXI: [...starters.slice(0, 10), player(20, "Newcomer")],
} as unknown as GameweekPlan;

test("explains who starts and that the sold player was on the bench", () => {
  render(<LineupEffect plan={plan} scenario={scenario} />);
  const note = screen.getByText(/Newcomer goes straight into your best XI/);
  expect(note).toHaveTextContent("Starter 11 moves to the bench");
  expect(note).toHaveTextContent("Benchy was on your bench");
});

test("the move badge shows the lineup gain, not in-minus-out points", () => {
  render(<MoveRow move={move} gain={2.3} />);
  expect(screen.getByText("your XI, next GW")).toBeInTheDocument();
  expect(screen.queryByText(/2\.4/)).not.toBeInTheDocument();
});
