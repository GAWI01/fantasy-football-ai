import { expect, test } from "vitest";

import { fdrLevel, parseOpponent, runScore } from "./fixtures";

test("parses explicit home and away markers", () => {
  expect(parseOpponent("CHE (H)")).toEqual({ short: "CHE", home: true });
  expect(parseOpponent("ars (a)")).toEqual({ short: "ars", home: false });
  expect(parseOpponent("TBC")).toEqual({ short: "TBC", home: null });
});

test("scores blanks as worse than any fixture and rewards doubles", () => {
  const team = (cells: Array<[number | null, number]>) => ({
    team_id: 1, team: "Club", team_short: "CLB",
    fixtures: cells.map(([difficulty, fixture_count], index) => ({ event: index + 1, opponents: [], difficulty, fixture_count })),
  });
  expect(runScore(team([[2, 1], [2, 1]]))).toBe(4);
  expect(runScore(team([[2, 1], [null, 0]]))).toBe(8);
  expect(runScore(team([[3, 2]]))).toBeLessThan(runScore(team([[3, 1]])));
  expect(fdrLevel(null)).toBe(0);
  expect(fdrLevel(4.6)).toBe(5);
});
