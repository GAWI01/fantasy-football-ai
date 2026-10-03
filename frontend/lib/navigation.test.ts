import { expect, test } from "vitest";

import { isActive, legacyModuleTarget, MOBILE_PRIMARY, NAV_ITEMS } from "./navigation";


test.each([
  ["my-team", "/team"],
  ["transfer-center", "/plan#transfers"],
  ["ai-recommendations", "/plan#why"],
  ["players", "/players"],
  ["fixtures", "/fixtures"],
  ["chips", "/plan#chips"],
  ["statistics", "/review"],
  ["team-history", "/review"],
  ["settings", "/settings"],
])("maps the legacy %s route to the canonical product surface", (module, target) => {
  expect(legacyModuleTarget(module)).toBe(target);
});


test("does not fabricate a destination for unknown modules", () => {
  expect(legacyModuleTarget("coming-soon")).toBeNull();
});


test("every mobile primary destination exists in the navigation model", () => {
  const keys = new Set(NAV_ITEMS.map((item) => item.key));
  for (const key of MOBILE_PRIMARY) expect(keys.has(key)).toBe(true);
});


test("overview is only active on the root path", () => {
  const overview = NAV_ITEMS[0];
  expect(isActive(overview, "/")).toBe(true);
  expect(isActive(overview, "/team")).toBe(false);
  expect(isActive({ href: "/plan" }, "/plan")).toBe(true);
});
