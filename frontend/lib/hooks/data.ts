"use client";

import { useMemo } from "react";
import { useTeam } from "@/app/providers/TeamProvider";

import { fetchChipPlan, fetchChipSquads, fetchLeagueCaptain, fetchPriceSwaps, fetchFixtureMatrix, fetchPriceChanges, fetchLeague, fetchLeagues, fetchPlayers, fetchReview, fetchRival } from "@/lib/api";
import type { ChipPlanEnvelope, ChipSquadsEnvelope, LeagueCaptainEnvelope, PriceSwapsEnvelope, FixtureMatrixEnvelope, PriceChangesEnvelope, LeagueEnvelope, LeaguesEnvelope, PlayerMarketEnvelope, PlayerSummary, ReviewEnvelope, RivalEnvelope } from "@/lib/contracts";
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


export function useLeagues(teamId: string | null) {
  return useResource<LeaguesEnvelope>(teamId ? `leagues:${teamId}` : null, (signal) => fetchLeagues(teamId ?? "", signal), 600_000);
}

export function useLeague(leagueId: number | null, teamId: string | null) {
  const version = useDataVersion();
  return useResource<LeagueEnvelope>(leagueId && teamId ? `league:${leagueId}:${teamId}:${version}` : null, (signal) => fetchLeague(leagueId ?? 0, teamId ?? "", signal), 300_000);
}

/** Captain candidates judged against one mini-league. */
export function useLeagueCaptain(leagueId: number | null, teamId: string | null, freeTransfers?: number | null) {
  const version = useDataVersion();
  return useResource<LeagueCaptainEnvelope>(leagueId && teamId ? `league-captain:${leagueId}:${teamId}:${freeTransfers ?? "est"}:${version}` : null, (signal) => fetchLeagueCaptain(leagueId ?? 0, teamId ?? "", freeTransfers, signal), 300_000);
}

export function useRival(leagueId: number | null, rivalId: number | null, teamId: string | null) {
  const version = useDataVersion();
  return useResource<RivalEnvelope>(leagueId && rivalId && teamId ? `rival:${leagueId}:${rivalId}:${teamId}:${version}` : null, (signal) => fetchRival(leagueId ?? 0, rivalId ?? 0, teamId ?? "", signal), 300_000);
}

/** Fetched only when asked for (a full rebuild takes a few seconds). */
export function useChipSquads(teamId: string | null, enabled: boolean, preferRisers = false) {
  const version = useDataVersion();
  return useResource<ChipSquadsEnvelope>(enabled && teamId ? `chip-squads:${teamId}:${preferRisers ? "risers" : "plain"}:${version}` : null, (signal) => fetchChipSquads(teamId ?? "", preferRisers, signal), 600_000);
}

/** When to play each chip for the rest of the period, from the fixture list. */
export function useChipPlan(teamId: string | null, freeTransfers?: number | null) {
  const version = useDataVersion();
  return useResource<ChipPlanEnvelope>(teamId ? `chip-plan:${teamId}:${freeTransfers ?? "est"}:${version}` : null, (signal) => fetchChipPlan(teamId ?? "", freeTransfers, signal), 600_000);
}

/** Swaps that sell a likely faller or buy a likely riser without losing points. */
export function usePriceSwaps(teamId: string | null, enabled: boolean, freeTransfers?: number | null) {
  const version = useDataVersion();
  return useResource<PriceSwapsEnvelope>(enabled && teamId ? `price-swaps:${teamId}:${freeTransfers ?? "est"}:${version}` : null, (signal) => fetchPriceSwaps(teamId ?? "", freeTransfers, signal), 300_000);
}

/** Official price-change figures; FPL updates them through the day. */
export function usePriceChanges(enabled = true) {
  return useResource<PriceChangesEnvelope>(enabled ? "price-changes" : null, (signal) => fetchPriceChanges(signal), 300_000);
}
