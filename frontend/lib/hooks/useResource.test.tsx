import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { clearResourceCache, useResource } from "./useResource";

beforeEach(() => { clearResourceCache(); vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

test("a mounted resource refreshes when its cached result expires", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce("GW6").mockResolvedValue("GW7");
  const { result } = renderHook(() => useResource("fixtures", fetcher, 1_000));
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(result.current.data).toBe("GW6");
  await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
  expect(result.current.data).toBe("GW7");
});

test("returning focus refreshes an expired resource after a hidden tab", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce("old").mockResolvedValue("new");
  const { result } = renderHook(() => useResource("players", fetcher, 1_000));
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
  await act(async () => { await vi.advanceTimersByTimeAsync(1_100); });
  expect(result.current.data).toBe("old");
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
  await act(async () => { window.dispatchEvent(new Event("focus")); });
  expect(result.current.data).toBe("new");
});

test("a failed refresh retains the last data and exposes the refresh error", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce("last good").mockRejectedValue(new Error("Service unavailable"));
  const { result } = renderHook(() => useResource("review", fetcher, 1_000));
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  await act(async () => { result.current.reload(); });
  expect(result.current).toMatchObject({ data: "last good", error: "Service unavailable", loading: false });
});
