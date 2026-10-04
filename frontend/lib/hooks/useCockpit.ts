"use client";

import { useMemo } from "react";

import { useTeam } from "@/app/providers/TeamProvider";
import { useMarketProjections } from "@/lib/hooks/data";
import { buildLiveView } from "@/lib/model/live";
import { useGameState } from "@/lib/hooks/useGameState";
import { buildPlan } from "@/lib/model/plan";
import { buildSquad } from "@/lib/model/squad";

/**
 * The single derived view of a connected team: game phase, merged squad,
 * gameweek plan and live summary. Pure derivations live in `lib/model`.
 */
export function useCockpit({ withMarket = true }: { withMarket?: boolean } = {}) {
  const team = useTeam();
  const { dashboard } = team;
  const market = useMarketProjections(withMarket && Boolean(dashboard?.data.decision));
  const state = useGameState(dashboard);
  const squad = useMemo(() => (dashboard ? buildSquad(dashboard.data) : []), [dashboard]);
  const plan = useMemo(
    () => (dashboard ? buildPlan(dashboard.data, squad, market.byId) : null),
    [dashboard, squad, market.byId],
  );
  const live = useMemo(() => (dashboard ? buildLiveView(dashboard.data, squad, dashboard.meta.prediction_event ?? dashboard.data.team.prediction_event) : null), [dashboard, squad]);
  return { ...team, state, squad, plan, live, marketLoading: market.loading };
}
