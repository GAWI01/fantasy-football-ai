import { expect, test } from "vitest";

import { cellCleanSheets, cleanSheetLevel, fdrLevel, parseOpponent, runCleanSheets, runScore } from "./fixtures";

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

test("expected clean sheets add up per fixture; a blank is zero and missing data is unknown", () => {
  const cell = (fixture_count: number, clean_sheet_chances?: number[]) => ({ event: 1, opponents: [], difficulty: 3, fixture_count, clean_sheet_chances });
  expect(cellCleanSheets(cell(1, [0.3]))).toBeCloseTo(0.3);
  expect(cellCleanSheets(cell(2, [0.3, 0.2]))).toBeCloseTo(0.5);
  expect(cellCleanSheets(cell(0, []))).toBe(0);
  expect(cellCleanSheets(cell(1))).toBeNull();
  const team = { team_id: 1, team: "Club", team_short: "CLB", fixtures: [{ ...cell(1, [0.4]), event: 1 }, { ...cell(1, [0.1]), event: 2 }] };
  expect(runCleanSheets(team)).toBeCloseTo(0.5);
  expect(cleanSheetLevel(0.45)).toBe(1);
  expect(cleanSheetLevel(0.05)).toBe(5);
  expect(cleanSheetLevel(null)).toBe(0);
});
