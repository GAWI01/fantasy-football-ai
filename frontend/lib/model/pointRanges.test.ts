import { expect, test } from "vitest";

import { pointRange, rangeLabel } from "./pointRanges";

test("ranges widen and hauls get likelier as expected points rise", () => {
  const low = pointRange(2)!;
  const high = pointRange(7)!;
  expect(high.high).toBeGreaterThan(low.high);
  expect(high.hauls).toBeGreaterThan(low.hauls);
  expect(pointRange(null)).toBeNull();
});

test("a captain's range doubles", () => {
  expect(rangeLabel(6.9)).toBe("2–10");
  expect(rangeLabel(6.9, 2)).toBe("4–20");
});
