import { act, renderHook } from "@testing-library/react";
import { expect, test } from "vitest";

import { resolveMotion, useCountUp } from "./motion";

test("the device's reduce-motion setting always wins; Auto means Lively", () => {
  expect(resolveMotion("auto", false)).toBe("lively");
  expect(resolveMotion("max", false)).toBe("max");
  expect(resolveMotion("calm", false)).toBe("calm");
  expect(resolveMotion("max", true)).toBe("off");
  expect(resolveMotion("auto", true)).toBe("off");
});

test("with motion off a number shows its value at once; it never counts", async () => {
  const { result, rerender } = renderHook(({ value }) => useCountUp(value, "off", { fromZero: true }), { initialProps: { value: 39 } });
  expect(result.current).toBe(39);
  rerender({ value: 45 });
  await act(async () => { await new Promise((resolve) => requestAnimationFrame(() => resolve(null))); });
  expect(result.current).toBe(45);
});

test("lively counts up from zero the first time", () => {
  const { result } = renderHook(() => useCountUp(39, "lively", { fromZero: true }));
  expect(result.current).toBe(0);
});
