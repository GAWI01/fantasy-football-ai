"use client";

import { useMemo } from "react";

import { fetchFixtureMatrix, fetchPlayers, fetchReview } from "@/lib/api";
import type { FixtureMatrixEnvelope, PlayerMarketEnvelope, PlayerSummary, ReviewEnvelope } from "@/lib/contracts";
import { useResource } from "@/lib/hooks/useResource";

export function usePlayerMarket() {
  return useResource<PlayerMarketEnvelope>("players:700", (signal) => fetchPlayers(700, signal), 120_000);
}

/** Public market rows (official facts plus next-GW model projection) by player id. */
export function useMarketProjections(enabled = true) {
  const market = useResource<PlayerMarketEnvelope>(enabled ? "players:700" : null, (signal) => fetchPlayers(700, signal), 120_000);
  const map = useMemo(
    () => new Map<number, PlayerSummary>((market.data?.data.players ?? []).map((player) => [player.player_id, player])),
    [market.data],
  );
  return { ...market, byId: map };
}

export function useFixtureMatrix(horizon = 6) {
  return useResource<FixtureMatrixEnvelope>(`fixture-matrix:${horizon}`, (signal) => fetchFixtureMatrix(horizon, signal), 300_000);
}

export function useReview(teamId: string | null, event?: number) {
  return useResource<ReviewEnvelope>(teamId ? `review:${teamId}:${event ?? "latest"}` : null, (signal) => fetchReview(teamId ?? "", event, signal), 300_000);
}
