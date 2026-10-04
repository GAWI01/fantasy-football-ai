"use client";

import { useMemo } from "react";
import { useTeam } from "@/app/providers/TeamProvider";

import { fetchFixtureMatrix, fetchPlayers, fetchReview } from "@/lib/api";
import type { FixtureMatrixEnvelope, PlayerMarketEnvelope, PlayerSummary, ReviewEnvelope } from "@/lib/contracts";
import { useResource } from "@/lib/hooks/useResource";

function useDataVersion() {
  const { dashboard } = useTeam();
  return [dashboard?.meta.current_event, dashboard?.meta.next_event, dashboard?.meta.prediction_event, dashboard?.meta.prediction_version].join(":");
}

export function usePlayerMarket() {
  const version = useDataVersion();
  return useResource<PlayerMarketEnvelope>(`players:700:${version}`, (signal) => fetchPlayers(700, signal), 120_000);
}

/** Public market rows (official facts plus next-GW model projection) by player id. */
export function useMarketProjections(enabled = true) {
  const version = useDataVersion();
  const { dashboard } = useTeam();
  const targetEvent = dashboard?.meta.prediction_event ?? dashboard?.data.team.prediction_event;
  const market = useResource<PlayerMarketEnvelope>(enabled ? `players:700:${version}` : null, (signal) => fetchPlayers(700, signal), 120_000);
  const map = useMemo(
    () => {
      const predictionEvent = market.data?.data.prediction_event ?? market.data?.data.next_event;
      const sameEvent = targetEvent != null && predictionEvent === targetEvent;
      return new Map<number, PlayerSummary>((market.data?.data.players ?? []).map((player) => [player.player_id, sameEvent ? player : {
        ...player, predicted_points: null, xmins: null, start_probability: null,
      }]));
    },
    [market.data, targetEvent],
  );
  return { ...market, byId: map };
}

export function useFixtureMatrix(horizon = 6) {
  const version = useDataVersion();
  return useResource<FixtureMatrixEnvelope>(`fixture-matrix:${horizon}:${version}`, (signal) => fetchFixtureMatrix(horizon, signal), 300_000);
}

export function useReview(teamId: string | null, event?: number) {
  const version = useDataVersion();
  return useResource<ReviewEnvelope>(teamId ? `review:${teamId}:${event ?? "latest"}:${version}` : null, (signal) => fetchReview(teamId ?? "", event, signal), 300_000);
}
