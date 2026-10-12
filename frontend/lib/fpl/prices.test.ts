import { expect, test } from "vitest";

import { countdown, isDrop, isRise, nextStatus, statusFromLikelihood } from "./prices";

test("maps FPL's likelihood scale to its own labels", () => {
  expect(statusFromLikelihood(5)).toBe("very-likely-rise");
  expect(statusFromLikelihood(4)).toBe("likely-rise");
  expect(statusFromLikelihood(3)).toBe("unlikely");
  expect(statusFromLikelihood(-3)).toBe("unlikely");
  expect(statusFromLikelihood(-4)).toBe("likely-drop");
  expect(statusFromLikelihood(-5)).toBe("very-likely-drop");
  expect(isRise("likely-rise") && isDrop("very-likely-drop")).toBe(true);
});

test("uses the next window and respects a price lock", () => {
  const projections = [{ offset: 1, percent: 140, likelihood: 5 }, { offset: 0, percent: 98, likelihood: 4 }];
  expect(nextStatus({ projections, locked_until: null })).toBe("likely-rise");
  expect(nextStatus({ projections, locked_until: "2026-10-17T21:00:00Z" })).toBe("locked");
  expect(nextStatus({ projections: [], locked_until: null })).toBe("unlikely");
});

test("counts down to the next change and stops once it has passed", () => {
  const now = Date.parse("2026-10-12T21:04:13Z");
  expect(countdown("2026-10-12T23:00:00Z", now)).toBe("01:55:47");
  expect(countdown("2026-10-12T20:00:00Z", now)).toBeNull();
  expect(countdown(null, now)).toBeNull();
});
