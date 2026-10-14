import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { InstallBanner, InstallSettings } from "@/components/install/InstallApp";
import { WELCOME_KEY } from "@/components/overview/WelcomeTips";

const IPHONE_SAFARI = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";

beforeEach(() => {
  window.localStorage.clear();
  vi.spyOn(window.navigator, "userAgent", "get").mockReturnValue(IPHONE_SAFARI);
});
afterEach(() => vi.restoreAllMocks());

test("Home waits for the welcome tips, then shows iPhone steps until closed", async () => {
  const { rerender } = render(<InstallBanner />);
  expect(screen.queryByText(/Add FF·AI to your Home Screen/)).not.toBeInTheDocument();
  window.localStorage.setItem(WELCOME_KEY, "1");
  rerender(<InstallBanner key="again" />);
  expect(screen.getByText(/Add FF·AI to your Home Screen/)).toBeInTheDocument();
  expect(screen.getByText(/Add to Home Screen/, { selector: "b" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Hide this tip" }));
  expect(screen.queryByText(/Add FF·AI to your Home Screen/)).not.toBeInTheDocument();
});

test("Settings keeps the steps after the Home card was closed", () => {
  window.localStorage.setItem("fpl-ai-install-dismissed", "1");
  render(<InstallSettings />);
  expect(screen.getByText(/Choose/)).toBeInTheDocument();
});
