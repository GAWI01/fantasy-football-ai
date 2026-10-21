import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ForecastsWorkspace } from "@/components/forecasts/ForecastsWorkspace";

const forecast = {
  fixture_id: 3, kickoff_time: "2026-10-24T14:00:00Z", started: false, finished: false, score: null,
  home: { id: 1, name: "North FC", short: "NOR", matches: 7 }, away: { id: 2, name: "South FC", short: "SOU", matches: 7 },
  expected_goals: { home: 1.71, away: 0.87 }, result: { home: 0.572, draw: 0.238, away: 0.19 },
  both_teams_score: 0.477, total_goals_over: { "1.5": 0.73, "2.5": 0.478, "3.5": 0.26 },
  team_goals_over: { home: { "0.5": 0.82, "1.5": 0.51 }, away: { "0.5": 0.58, "1.5": 0.22 } },
  clean_sheet: { home: 0.42, away: 0.18 }, likely_scores: [{ home: 1, away: 0, probability: 0.129 }],
};

vi.mock("@/lib/hooks/data", () => ({
  useMatchForecasts: () => ({
    data: { data: { event: 8, current_event: 7, next_event: 8, fixtures: [forecast], backtest: {
      matches: 1140, seasons: ["2023-24", "2024-25", "2025-26"],
      result: { log_loss_model: 0.995, log_loss_base_rates: 1.072, hit_rate_model: 0.518, draws_actual: 0.245, draws_predicted: 0.233 },
      both_teams_score: { brier_model: 0.245, brier_base_rate: 0.243 }, over_2_5: { brier_model: 0.244, brier_base_rate: 0.242 } } },
      meta: { source: "model" }, errors: [] },
    loading: false, error: null, reload: vi.fn(),
  }),
}));
vi.mock("@/components/shell/PageTabs", () => ({ PageLinkTabs: () => null }));

afterEach(() => vi.clearAllMocks());

test("shows each match's chances, marks weak markets and says it is not betting advice", () => {
  render(<ForecastsWorkspace />);
  expect(screen.getAllByText("Gameweek 8").length).toBeGreaterThan(0);
  expect(screen.getByRole("img", { name: /NOR win 57%, draw 24%, SOU win 19%/ })).toBeInTheDocument();
  expect(screen.getByText("1–0")).toBeInTheDocument();
  expect(screen.getAllByText("rough", { selector: "small" })).toHaveLength(2);
  expect(screen.getByText(/not betting advice/)).toBeInTheDocument();
  expect(screen.getByText(/1,140 past Premier League matches/)).toBeInTheDocument();
});

test("offers no past Gameweeks, which would be judged with hindsight", () => {
  render(<ForecastsWorkspace />);
  expect(screen.getByRole("button", { name: "Previous Gameweek" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Next Gameweek" })).toBeEnabled();
});
