import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { DeadlineCountdown, formatDeadlineRemaining } from "./DeadlineCountdown";


test("formats a deadline as a compact live countdown", () => {
  const now = Date.parse("2026-09-01T10:00:00Z");

  expect(formatDeadlineRemaining("2026-09-03T17:30:00Z", now)).toBe("2d 07h 30m 00s");
  expect(formatDeadlineRemaining("2026-09-01T13:05:09Z", now)).toBe("3h 05m 09s");
  expect(formatDeadlineRemaining("2026-09-01T10:00:59Z", now)).toBe("59s");
  expect(formatDeadlineRemaining("2026-09-01T09:59:59Z", now)).toBe("Deadline passed");
});


test("labels the target gameweek and official deadline", () => {
  render(
    <DeadlineCountdown
      deadline="2026-09-03T17:30:00Z"
      event={3}
      now={Date.parse("2026-09-01T10:00:00Z")}
    />,
  );

  expect(screen.getByText("GW3 deadline")).toBeInTheDocument();
  expect(screen.getByText("2d 07h 30m 00s")).toBeInTheDocument();
  expect(screen.getByRole("timer")).toHaveAttribute(
    "dateTime",
    "2026-09-03T17:30:00Z",
  );
});


afterEach(() => {
  vi.useRealTimers();
});


test("ticks down every second while days remain", () => {
  vi.useFakeTimers();
  vi.setSystemTime(Date.parse("2026-10-03T17:00:00Z"));
  render(<DeadlineCountdown deadline="2026-10-10T10:00:00Z" event={6} />);

  act(() => {
    vi.advanceTimersByTime(0);
  });
  expect(screen.getByRole("timer")).toHaveTextContent("6d 17h 00m 00s");

  act(() => {
    vi.advanceTimersByTime(1_000);
  });
  expect(screen.getByRole("timer")).toHaveTextContent("6d 16h 59m 59s");

  act(() => {
    vi.advanceTimersByTime(5_000);
  });
  expect(screen.getByRole("timer")).toHaveTextContent("6d 16h 59m 54s");
});
