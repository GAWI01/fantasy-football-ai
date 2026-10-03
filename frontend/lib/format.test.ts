import { expect, test } from "vitest";

import { compact, fixed, percent, price, signed } from "./format";

test("formats missing values as a dash rather than zero", () => {
  expect(fixed(null)).toBe("—");
  expect(price(undefined)).toBe("—");
  expect(percent(null)).toBe("—");
});

test("formats numbers for FPL display", () => {
  expect(price(7.5)).toBe("£7.5m");
  expect(signed(2.345)).toBe("+2.3");
  expect(signed(-1.2)).toBe("−1.2");
  expect(percent(0.42, { fraction: true })).toBe("42%");
  expect(compact(431000)).toMatch(/431K/i);
});
