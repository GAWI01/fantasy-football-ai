import { expect, test } from "vitest";

import { overrideApplies, parseFreeTransferOverride } from "./freeTransfers";

test("parses a stored free-transfer count and rejects invalid values", () => {
  expect(parseFreeTransferOverride(JSON.stringify({ teamId: "123", event: 6, value: 0 }))).toEqual({ teamId: "123", event: 6, value: 0 });
  expect(parseFreeTransferOverride(JSON.stringify({ teamId: "123", event: 6, value: 6 }))).toBeNull();
  expect(parseFreeTransferOverride(JSON.stringify({ teamId: "123", value: 1.5 }))).toBeNull();
  expect(parseFreeTransferOverride("not json")).toBeNull();
  expect(parseFreeTransferOverride(null)).toBeNull();
});

test("a count set for an earlier Gameweek no longer applies", () => {
  const override = { teamId: "123", event: 6, value: 0 };
  expect(overrideApplies(override, 6)).toBe(true);
  expect(overrideApplies(override, 7)).toBe(false);
  expect(overrideApplies({ ...override, event: null }, 7)).toBe(true);
  expect(overrideApplies(null, 6)).toBe(false);
});
