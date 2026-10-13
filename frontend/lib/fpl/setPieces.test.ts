import { expect, test } from "vitest";

import { setPieceRoles, setPieceTag } from "./setPieces";

test("lists first-choice set pieces first and marks back-ups", () => {
  expect(setPieceRoles({ penalties_order: 1, direct_freekicks_order: 2, corners_order: null })).toEqual(["Penalties", "Free kicks (2nd)"]);
  expect(setPieceRoles({ penalties_order: 4, direct_freekicks_order: null, corners_order: null })).toEqual([]);
  expect(setPieceTag({ penalties_order: 1, direct_freekicks_order: 1, corners_order: 1 })).toBe("Pens");
  expect(setPieceTag({ penalties_order: 2, direct_freekicks_order: null, corners_order: 1 })).toBeNull();
});
