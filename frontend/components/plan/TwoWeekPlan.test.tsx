import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import type { TwoWeekPlan } from "@/lib/contracts";
import { NextWeekLine, TwoWeekCard } from "./TwoWeekPlan";

function planFixture(): TwoWeekPlan {
  return Object.assign({ best_transfers_now: 2, sequences: [
    Object.assign({ transfers_now: 1, moves_now: [{ player_out_id: 109, player_out: "Ekström", player_in_id: 201, player_in: "Castellano", position: "MID" }], moves_next: [{ player_out_id: 111, player_out: "Adeyemi", player_in_id: 202, player_in: "Brennan", position: "FWD" }], free_transfers_next: 1, hits_now: 0, hits_next: 1, score_vs_hold: 2.5 }, { projected_gain: 12.75, projected_net_gain: 8.75, weighted_gain_vs_hold: 10.5, hit_cost: 4, risk_margin: 2, roll_value: 2, recommended: true }),
    Object.assign({ transfers_now: 2, moves_now: [], moves_next: [], free_transfers_next: 1, hits_now: 1, hits_next: 0, score_vs_hold: 3.5 }, { projected_gain: 14, projected_net_gain: 10, weighted_gain_vs_hold: 12, hit_cost: 4, risk_margin: 2, roll_value: 1, recommended: false }),
  ] }, { horizon: 5, weights: [1, 0.9, 0.8, 0.7, 0.6], selection_policy: "conservative" as const, recommended_transfers_now: 1, optimality_known: false, baseline: "hold_now_then_optimize" as const });
}

test("separates projected FPL gains from weighted decision scores and policy values", () => {
  const { container } = render(<TwoWeekCard plan={planFixture()} transfersNow={1} />);
  const row = screen.getByText("1 now").closest("li")!;
  expect(within(row).getByText(/Projected net gain/)).toHaveTextContent("+8.8 xP");
  expect(within(row).getByText(/Decision score/)).toHaveTextContent("+2.5");
  expect(row).toHaveTextContent("Hit cost: −4");
  expect(row).toHaveTextContent("Safety margin: 2.0");
  expect(row).toHaveTextContent("Terminal roll value: 2.0");
  expect(container).toHaveTextContent("1, 0.9, 0.8, 0.7, 0.6");
  expect(container).toHaveTextContent(/hold now, then optimize next week/i);
  expect(container).toHaveTextContent(/optimality is unconfirmed/i);
  expect(container).not.toHaveTextContent(/each row is the best plan/i);
});

test("follow-up moves explicitly depend on today's information", () => {
  render(<NextWeekLine plan={planFixture()} transfersNow={1} />);
  expect(screen.getByText(/if current info holds/i).closest("p")).toHaveTextContent("Adeyemi → Brennan");
});

test("old payloads show unavailable projected points instead of relabelling the score", () => {
  const plan = planFixture();
  const sequence = plan.sequences[0];
  delete (sequence as { projected_net_gain?: number }).projected_net_gain;
  const { container } = render(<TwoWeekCard plan={{ ...plan, horizon: 2, weights: [1, 0.9], sequences: [sequence] } as TwoWeekPlan} transfersNow={1} />);
  expect(screen.getByText(/Projected net gain/)).toHaveTextContent("Unavailable");
  expect(container).toHaveTextContent("Scores cover the next 2 Gameweeks");
});

test("an incomplete solve keeps its status visible when no follow-up was returned", () => {
  render(<TwoWeekCard plan={{ ...planFixture(), sequences: [], optimality_known: false }} transfersNow={1} />);
  expect(screen.getByText("No follow-up sequence was returned.")).toBeInTheDocument();
  expect(screen.getByText(/optimality is unconfirmed/i)).toBeInTheDocument();
  expect(screen.queryByText("Recommended")).not.toBeInTheDocument();
});
