import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { makeDashboard } from "@/test-utils/fixtures";
import { useGameState } from "./useGameState";

afterEach(() => vi.useRealTimers());

test("the mounted action lock reacts at the deadline without a dashboard refresh", async () => {
  vi.useFakeTimers();
  vi.setSystemTime("2026-10-04T09:59:59Z");
  const dashboard = makeDashboard();
  dashboard.meta.target_deadline_time = "2026-10-04T10:00:00Z";
  const { result } = renderHook(() => useGameState(dashboard));
  expect(result.current.actionsOpen).toBe(true);
  await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
  expect(result.current.actionsOpen).toBe(false);
});
