import { expect, test } from "vitest";

import { availabilityFromStatus, formationLabel, hitCost, normalizePosition, validateStartingXI } from "./rules";

const xi = (gk: number, def: number, mid: number, fwd: number) => [
  ...Array(gk).fill({ position: "GKP" }),
  ...Array(def).fill({ position: "DEF" }),
  ...Array(mid).fill({ position: "MID" }),
  ...Array(fwd).fill({ position: "FWD" }),
];

test("normalizes official and model position codes to one vocabulary", () => {
  expect(normalizePosition("GK")).toBe("GKP");
  expect(normalizePosition("GKP")).toBe("GKP");
  expect(normalizePosition(1)).toBe("GKP");
  expect(normalizePosition("mid")).toBe("MID");
  expect(normalizePosition("winger")).toBeNull();
});

test("accepts every legal FPL formation and rejects illegal ones with a reason", () => {
  expect(validateStartingXI(xi(1, 3, 4, 3)).valid).toBe(true);
  expect(validateStartingXI(xi(1, 5, 2, 3)).valid).toBe(true);
  expect(validateStartingXI(xi(1, 5, 4, 1)).valid).toBe(true);
  expect(validateStartingXI(xi(1, 2, 5, 3))).toMatchObject({ valid: false });
  expect(validateStartingXI(xi(2, 3, 4, 2)).reason).toMatch(/goalkeeper/i);
  expect(validateStartingXI(xi(1, 5, 5, 0)).reason).toMatch(/forward/i);
  expect(validateStartingXI(xi(1, 4, 4, 1)).valid).toBe(false);
  expect(formationLabel(xi(1, 4, 4, 2))).toBe("4-4-2");
});

test("charges four points per transfer beyond the free allowance and never guesses", () => {
  expect(hitCost(1, 1)).toBe(0);
  expect(hitCost(3, 1)).toBe(8);
  expect(hitCost(2, null)).toBeNull();
});

test("maps official status codes to labelled availability", () => {
  expect(availabilityFromStatus("a")).toEqual({ label: "Available", tone: "ok" });
  expect(availabilityFromStatus("d", 75)).toEqual({ label: "75% chance", tone: "warn" });
  expect(availabilityFromStatus("d", 25).tone).toBe("risk");
  expect(availabilityFromStatus("i").label).toBe("Injured");
  expect(availabilityFromStatus(undefined).tone).toBe("unknown");
});
