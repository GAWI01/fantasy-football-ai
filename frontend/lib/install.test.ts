import { expect, test } from "vitest";

import { detectPlatform } from "@/lib/install";

const nav = (userAgent: string, extra: { maxTouchPoints?: number; standalone?: boolean } = {}) =>
  ({ userAgent, maxTouchPoints: extra.maxTouchPoints ?? 0, standalone: extra.standalone });
const IPHONE_SAFARI = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";

test("an already-installed app shows nothing", () => {
  expect(detectPlatform(nav(IPHONE_SAFARI, { standalone: true }), false, false)).toBe("installed");
  expect(detectPlatform(nav("Android Chrome"), true, true)).toBe("installed");
});

test("a browser with an install prompt gets the button", () => {
  expect(detectPlatform(nav("Mozilla/5.0 (Linux; Android 15) Chrome/130"), false, true)).toBe("prompt");
});

test("iPhone Safari gets steps; other iPhone browsers are sent to Safari", () => {
  expect(detectPlatform(nav(IPHONE_SAFARI), false, false)).toBe("ios-safari");
  expect(detectPlatform(nav(IPHONE_SAFARI.replace("Version/18.0", "CriOS/130.0")), false, false)).toBe("ios-other");
  expect(detectPlatform(nav(`${IPHONE_SAFARI} Instagram 300.0`), false, false)).toBe("ios-other");
});

test("iPad reporting a Mac user agent counts as iOS; a real Mac does not", () => {
  const mac = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15";
  expect(detectPlatform(nav(mac, { maxTouchPoints: 5 }), false, false)).toBe("ios-safari");
  expect(detectPlatform(nav(mac), false, false)).toBe("unsupported");
});
