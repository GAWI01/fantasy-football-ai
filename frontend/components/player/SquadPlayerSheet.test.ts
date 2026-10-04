import { expect, test } from "vitest";

import { mainRiskFor } from "@/lib/model/plan";
import { buildSquad } from "@/lib/model/squad";
import { makeDashboard } from "@/test-utils/fixtures";
import { modelRead } from "./SquadPlayerSheet";

test("missing minutes signals do not become a stable-minutes claim", () => {
  const player = buildSquad(makeDashboard().data).find((player) => player.id === 107)!;
  Object.assign(player, { xmins: null, startProbability: null, risk: null, modelAvailability: null, difficulty: 2 });
  expect(modelRead(player)).toContain("Minutes forecast unavailable");
});

test("one known bench risk cannot imply complete starter risk coverage", () => {
  const squad = buildSquad(makeDashboard().data);
  for (const player of squad.filter((player) => player.isStarter)) {
    Object.assign(player, { status: "a", chance: null, risk: null, modelAvailability: null, rotationRisk: null, xmins: null, startProbability: null });
  }
  expect(mainRiskFor(squad, null).title).toBe("Risk model unavailable");
});
