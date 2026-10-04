import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { TeamProvider, useTeam } from "./TeamProvider";


const dashboard = {
  data: {
    team: {
      team_id: 123,
      name: "Test XI",
      bank: 10,
      event: 2,
      transfers: 0,
      picks: [],
    },
    live: null,
    history: { history: [] },
    fixtures: { fixtures: [] },
    players: { players: [] },
    decision: null,
  },
  meta: {
    event: 2,
    generated_at: "2026-08-31T18:00:00+00:00",
    degraded: false,
  },
  errors: [],
};


function Probe() {
  const [value, setValue] = useState("");
  const { connect, dashboard: result, loading } = useTeam();
  return (
    <div>
      <label htmlFor="team-id">Team ID</label>
      <input id="team-id" value={value} onChange={(event) => setValue(event.target.value)} />
      <button type="button" onClick={() => void connect(value)}>Connect</button>
      {loading ? <span>Loading</span> : null}
      {result ? <span>{result.data.team.name}</span> : null}
    </div>
  );
}


beforeEach(() => {
  localStorage.clear();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(dashboard), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
});


afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});


test("connect persists a valid Team ID and loads the dashboard", async () => {
  const user = userEvent.setup();
  render(<TeamProvider><Probe /></TeamProvider>);

  await user.type(screen.getByLabelText(/team id/i), "123");
  await user.click(screen.getByRole("button", { name: /connect/i }));

  expect(localStorage.getItem("fpl-ai-team-id")).toBe("123");
  expect(await screen.findByText("Test XI")).toBeInTheDocument();
});


test("disconnect clears the selected Team ID and dashboard", async () => {
  const user = userEvent.setup();
  localStorage.setItem("fpl-ai-team-id", "123");
  function DisconnectProbe() {
    const team = useTeam();
    return <><span>{team.dashboard?.data.team.name ?? "No team"}</span><button onClick={team.disconnect}>Disconnect</button></>;
  }
  render(<TeamProvider><DisconnectProbe /></TeamProvider>);
  expect(await screen.findByText("Test XI")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Disconnect" }));

  expect(localStorage.getItem("fpl-ai-team-id")).toBeNull();
  expect(screen.getByText("No team")).toBeInTheDocument();
});


function FreeTransferProbe() {
  const { connect, setFreeTransfers, refresh } = useTeam();
  return (
    <div>
      <button type="button" onClick={() => void connect("123")}>Connect</button>
      <button type="button" onClick={() => void setFreeTransfers(0)}>Set zero</button>
      <button type="button" onClick={() => void setFreeTransfers(null)}>Use estimate</button>
      <button type="button" onClick={() => void refresh()}>Refresh</button>
    </div>
  );
}


function respondWith(predictionEvent: number) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(
    JSON.stringify({ ...dashboard, meta: { ...dashboard.meta, prediction_event: predictionEvent } }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  ));
}


test("a manager-set free-transfer count is sent with every dashboard load", async () => {
  const fetchSpy = respondWith(6);
  const user = userEvent.setup();
  render(<TeamProvider><FreeTransferProbe /></TeamProvider>);

  await user.click(screen.getByRole("button", { name: "Connect" }));
  expect(fetchSpy).toHaveBeenLastCalledWith("/api/v1/dashboard/123", expect.anything());

  await user.click(screen.getByRole("button", { name: "Set zero" }));
  expect(fetchSpy).toHaveBeenLastCalledWith("/api/v1/dashboard/123?free_transfers=0", expect.anything());
  expect(JSON.parse(localStorage.getItem("fpl-ai-free-transfers") ?? "null")).toEqual({ teamId: "123", event: 6, value: 0 });

  await user.click(screen.getByRole("button", { name: "Use estimate" }));
  expect(fetchSpy).toHaveBeenLastCalledWith("/api/v1/dashboard/123", expect.anything());
  expect(localStorage.getItem("fpl-ai-free-transfers")).toBeNull();
});


test("a free-transfer count from an earlier Gameweek is dropped", async () => {
  localStorage.setItem("fpl-ai-free-transfers", JSON.stringify({ teamId: "123", event: 6, value: 0 }));
  const fetchSpy = respondWith(7);
  const user = userEvent.setup();
  render(<TeamProvider><FreeTransferProbe /></TeamProvider>);

  await user.click(screen.getByRole("button", { name: "Connect" }));

  expect(fetchSpy).toHaveBeenNthCalledWith(1, "/api/v1/dashboard/123?free_transfers=0", expect.anything());
  expect(fetchSpy).toHaveBeenLastCalledWith("/api/v1/dashboard/123", expect.anything());
  expect(localStorage.getItem("fpl-ai-free-transfers")).toBeNull();
});

test("a manager-set free-transfer count survives blocked browser storage for this session", async () => {
  const fetchSpy = respondWith(6);
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("Storage blocked"); });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Storage blocked"); });
  const user = userEvent.setup();
  render(<TeamProvider><FreeTransferProbe /></TeamProvider>);
  await user.click(screen.getByRole("button", { name: "Connect" }));
  await user.click(screen.getByRole("button", { name: "Set zero" }));
  expect(fetchSpy).toHaveBeenLastCalledWith("/api/v1/dashboard/123?free_transfers=0", expect.anything());
  await user.click(screen.getByRole("button", { name: "Refresh" }));
  expect(fetchSpy).toHaveBeenLastCalledWith("/api/v1/dashboard/123?free_transfers=0", expect.anything());
});

test("an override with an unknown event binds to the first known Gameweek and expires on rollover", async () => {
  localStorage.setItem("fpl-ai-free-transfers", JSON.stringify({ teamId: "123", event: null, value: 0 }));
  const fetchSpy = respondWith(6);
  const user = userEvent.setup();
  render(<TeamProvider><FreeTransferProbe /></TeamProvider>);
  await user.click(screen.getByRole("button", { name: "Connect" }));
  expect(JSON.parse(localStorage.getItem("fpl-ai-free-transfers") ?? "null")).toEqual({ teamId: "123", event: 6, value: 0 });
  fetchSpy.mockImplementation(async () => new Response(JSON.stringify({ ...dashboard, meta: { ...dashboard.meta, prediction_event: 7 } }), { status: 200 }));
  await user.click(screen.getByRole("button", { name: "Refresh" }));
  expect(fetchSpy).toHaveBeenLastCalledWith("/api/v1/dashboard/123", expect.anything());
  expect(localStorage.getItem("fpl-ai-free-transfers")).toBeNull();
});

test("an unknown-event override binds to the official next Gameweek when the model event is missing", async () => {
  localStorage.setItem("fpl-ai-free-transfers", JSON.stringify({ teamId: "123", event: null, value: 0 }));
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ ...dashboard, meta: { ...dashboard.meta, next_event: 6 } }), { status: 200 }));
  render(<TeamProvider><FreeTransferProbe /></TeamProvider>);
  await userEvent.click(screen.getByRole("button", { name: "Connect" }));
  expect(JSON.parse(localStorage.getItem("fpl-ai-free-transfers") ?? "null")).toEqual({ teamId: "123", event: 6, value: 0 });
});
