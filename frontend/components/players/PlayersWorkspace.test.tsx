import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { TeamProvider } from "@/app/providers/TeamProvider";
import { makePlayerMarket } from "@/test-utils/fixtures";
import { mockApi } from "@/test-utils/mockApi";
import { PlayersWorkspace } from "./PlayersWorkspace";

afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

test("public player forecasts are visibly unverified without connecting a team", async () => {
  localStorage.clear();
  const fetchSpy = mockApi();
  const route = fetchSpy.getMockImplementation()!;
  fetchSpy.mockImplementation(async (input, init) => {
    if (String(input).includes("/players")) {
      const market = makePlayerMarket();
      market.data.model_validation_state = "unverified";
      return new Response(JSON.stringify(market), { status: 200 });
    }
    return route(input, init);
  });
  render(<TeamProvider><PlayersWorkspace /></TeamProvider>);
  expect(await screen.findByText("Unverified model forecasts")).toBeInTheDocument();
});
