import { expect, test } from "vitest";

import { CLUBS } from "@/test-utils/fixtures";
import { clubCode, kitDesign } from "./kits";

test("every 2026-27 club has its own original kit design", () => {
  const signatures = CLUBS.map(([short, name]) => {
    const design = kitDesign(name, short);
    expect(design.code).toBe(short);
    return `${design.body}|${design.detail}|${design.pattern}`;
  });
  expect(new Set(signatures).size).toBe(CLUBS.length);
});

test("resolves clubs from names when the short code is missing", () => {
  expect(clubCode("Nott'm Forest")).toBe("NFO");
  expect(clubCode("Manchester United")).toBe("MUN");
  expect(clubCode("Spurs")).toBe("TOT");
});

test("unknown clubs fall back to a neutral kit and goalkeepers share one palette", () => {
  expect(kitDesign("Atlantis Rovers", "ATL").pattern).toBe("plain");
  const keeper = kitDesign("Arsenal", "ARS", true);
  expect(keeper.pattern).toBe("pinstripe");
  expect(keeper.trim).toBe(kitDesign("Arsenal", "ARS").body);
  expect(kitDesign("Chelsea", "CHE", true).body).toBe(keeper.body);
});
