import { afterEach, beforeEach, expect, test } from "vitest";

import { readPlanHistory, recordPlanSnapshot, type PlanSnapshot } from "./planHistory";


const base: PlanSnapshot = {
  event: 3,
  action: "Saka → Palmer",
  captain: "Palmer",
  netGain: 2.8,
  confidenceScore: 0.62,
  confidenceLabel: "MEDIUM",
  modelVersion: "gw3_predictions_v11.csv",
  recordedAt: "2026-09-01T10:00:00Z",
};


beforeEach(() => localStorage.clear());
afterEach(() => localStorage.clear());


test("records decision changes but deduplicates identical refreshes", () => {
  recordPlanSnapshot(localStorage, base, "123");
  recordPlanSnapshot(localStorage, { ...base, recordedAt: "2026-09-01T10:05:00Z" }, "123");
  recordPlanSnapshot(localStorage, {
    ...base,
    action: "Hold the transfer",
    netGain: 0,
    recordedAt: "2026-09-01T12:00:00Z",
  }, "123");

  const history = readPlanHistory(localStorage, "123");
  expect(history).toHaveLength(2);
  expect(history[0].action).toBe("Hold the transfer");
  expect(history[1].action).toBe("Saka → Palmer");
});


test("ignores tiny model refreshes but records a meaningful uncertainty change", () => {
  recordPlanSnapshot(localStorage, base, "123");
  recordPlanSnapshot(localStorage, {
    ...base,
    netGain: 2.9,
    confidenceScore: 0.64,
    modelVersion: "gw3_predictions_v12.csv",
    recordedAt: "2026-09-01T10:05:00Z",
  }, "123");
  expect(readPlanHistory(localStorage, "123")).toHaveLength(1);

  recordPlanSnapshot(localStorage, {
    ...base,
    confidenceScore: 0.78,
    confidenceLabel: "HIGH",
    modelVersion: "gw3_predictions_v13.csv",
    recordedAt: "2026-09-01T11:00:00Z",
  }, "123");

  expect(readPlanHistory(localStorage, "123")).toHaveLength(2);
  expect(readPlanHistory(localStorage, "123")[0].confidenceLabel).toBe("HIGH");
});


test("keeps only the six most recent local decision snapshots", () => {
  for (let index = 0; index < 8; index += 1) {
    recordPlanSnapshot(localStorage, {
      ...base,
      action: `Decision ${index}`,
      recordedAt: `2026-09-01T${String(index).padStart(2, "0")}:00:00Z`,
    }, "123");
  }

  const history = readPlanHistory(localStorage, "123");
  expect(history).toHaveLength(6);
  expect(history[0].action).toBe("Decision 7");
  expect(history[5].action).toBe("Decision 2");
});


test("treats invalid local data as empty history", () => {
  localStorage.setItem("fpl-ai-plan-history:123", "not-json");

  expect(readPlanHistory(localStorage, "123")).toEqual([]);
});

test("switching Team IDs cannot show another manager's decision history", () => {
  recordPlanSnapshot(localStorage, base, "123");
  recordPlanSnapshot(localStorage, { ...base, action: "Hold", captain: "Duarte" }, "456");
  expect(readPlanHistory(localStorage, "123").map((snapshot) => snapshot.action)).toEqual(["Saka → Palmer"]);
  expect(readPlanHistory(localStorage, "456").map((snapshot) => snapshot.action)).toEqual(["Hold"]);
});
