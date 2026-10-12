import { renderHook } from "@testing-library/react";
import { expect, test } from "vitest";

import type { DashboardLive, LiveEvent } from "@/lib/contracts";
import { useLiveMoments } from "./useLiveMoments";

function event(playerId: number, type: LiveEvent["event_type"], count: number, active = true): LiveEvent {
  return { player_id: playerId, player_name: `Player ${playerId}`, team_short: "ABC", event_type: type, count, active, provisional: false };
}

function live(events: LiveEvent[], currentEvent = 6): DashboardLive {
  return { current_event: currentEvent, status: "LIVE", picks: [], events };
}

test("the first load sets a baseline: nothing that already happened is announced", () => {
  const { result } = renderHook(({ data }) => useLiveMoments(data), { initialProps: { data: live([event(1, "GOAL", 2)]) } });
  expect(result.current).toBeNull();
});

test("a new goal by one of your active picks becomes a moment; a goal outranks an assist", () => {
  const { result, rerender } = renderHook(({ data }) => useLiveMoments(data), { initialProps: { data: live([event(1, "GOAL", 1), event(2, "ASSIST", 0)]) } });
  rerender({ data: live([event(1, "GOAL", 1), event(2, "ASSIST", 1), event(3, "GOAL", 1)]) });
  expect(result.current).toMatchObject({ kind: "goal", playerId: 3, count: 1 });
  const first = result.current?.id;

  rerender({ data: live([event(1, "GOAL", 1), event(2, "ASSIST", 2), event(3, "GOAL", 1)]) });
  expect(result.current).toMatchObject({ kind: "assist", playerId: 2 });
  expect(result.current?.id).not.toBe(first);
});

test("benched players and a new Gameweek do not trigger moments", () => {
  const { result, rerender } = renderHook(({ data }) => useLiveMoments(data), { initialProps: { data: live([event(9, "GOAL", 0, false)]) } });
  rerender({ data: live([event(9, "GOAL", 1, false)]) });
  expect(result.current).toBeNull();
  // A new Gameweek starts a new baseline.
  rerender({ data: live([event(4, "GOAL", 1)], 7) });
  expect(result.current).toBeNull();
});
