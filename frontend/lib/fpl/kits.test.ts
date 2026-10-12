import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";

import { CLUBS } from "@/test-utils/fixtures";
import { CLUB_KIT_PATTERNS, KIT_CLUB_CODES, clubCode, kitDesign } from "./kits";

const HEX = /^#[0-9a-f]{6}$/i;
const FORBIDDEN = /\b(official|authentic|replica)\b|\b20\d\d\/\d\d kit\b/i;
const allKits = () => KIT_CLUB_CODES.map((code) => kitDesign(null, code));

test("every club has a valid layout and colours", () => {
  for (const kit of allKits()) {
    expect(CLUB_KIT_PATTERNS).toContain(kit.pattern);
    for (const colour of [kit.body, kit.detail, kit.trim, kit.ink]) expect(colour).toMatch(HEX);
    if (kit.pattern === "sleeves") expect(kit.sleeves).toMatch(HEX);
  }
  for (const [short, name] of CLUBS) {
    expect(KIT_CLUB_CODES).toContain(short);
    expect(kitDesign(name, short).code).toBe(short);
  }
});

test("striped kits have at least three stripes", () => {
  const striped = allKits().filter((kit) => kit.pattern === "stripes");
  expect(striped.length).toBeGreaterThan(0);
  for (const kit of striped) expect(kit.stripes ?? 5).toBeGreaterThanOrEqual(3);
});

test("kit data and kit sources never claim to be official designs", () => {
  expect(JSON.stringify(allKits())).not.toMatch(FORBIDDEN);
  for (const file of ["./kits.ts", "../../components/kit/Kit.tsx"]) {
    expect(readFileSync(fileURLToPath(new URL(file, import.meta.url)), "utf8")).not.toMatch(FORBIDDEN);
  }
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
