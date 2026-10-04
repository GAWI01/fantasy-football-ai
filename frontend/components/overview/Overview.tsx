"use client";

import { ArrowRight, History, LineChart, Shirt } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { TrendChart } from "@/components/charts/TrendChart";
import { SquadFixtures } from "@/components/fixtures/SquadFixtures";
import { ConnectHero } from "@/components/overview/ConnectHero";
import { GameweekPlanCard } from "@/components/overview/GameweekPlanCard";
import { LiveCockpit } from "@/components/overview/LiveCockpit";
import { FormationRows, PitchPlayer, PitchSurface } from "@/components/pitch/Pitch";
import { DataState } from "@/components/states/DataState";
import { Card, Segmented, SourceBadge, Stat } from "@/components/ui/primitives";
import { compact, integer, price, signed } from "@/lib/format";
import { useCockpit } from "@/lib/hooks/useCockpit";
import { usePlanHistory } from "@/lib/hooks/usePlanHistory";
import { liveSource, officialSource } from "@/lib/model/phase";
import { planSnapshot } from "@/lib/model/plan";

type View = "live" | "plan";

export function OverviewSkeleton() {
  return (
    <div className="stack" aria-busy="true">
      <DataState title="Loading your cockpit" loading>Fetching your official squad, live scores and the latest model plan.</DataState>
    </div>
  );
}

export function Overview() {
  const cockpit = useCockpit();
  const { ready, dashboard, loading, error, teamId, refresh, disconnect, state, squad, plan, live } = cockpit;
  const [view, setView] = useState<View | null>(null);
  const snapshot = useMemo(
    () => (plan && state.actionsOpen && dashboard ? planSnapshot(plan, state.targetEvent, state.modelVersion, dashboard.meta.generated_at) : null),
    [plan, state.actionsOpen, state.targetEvent, state.modelVersion, dashboard],
  );
  const { change } = usePlanHistory(snapshot, teamId);

  if (!ready || (!dashboard && loading)) return <OverviewSkeleton />;
  if (!dashboard && teamId && error) {
    return (
      <DataState tone="error" title="Your team could not be loaded" action={<><button className="btn btn-sm btn-primary" onClick={() => void refresh()}>Try again</button><button className="btn btn-sm" onClick={disconnect}>Use another Team ID</button></>}>
        {error}
      </DataState>
    );
  }
  if (!dashboard) return <ConnectHero />;

  const team = dashboard.data.team;
  const history = dashboard.data.history?.history ?? [];
  const canShowLive = state.liveActive && live != null;
  const canShowPlan = plan != null;
  const activeView: View = view ?? (canShowLive ? "live" : "plan");
  const showToggle = canShowLive && canShowPlan && state.actionsOpen;
  const lastGw = history[history.length - 1];

  return (
    <div className="overview">
      <header className="page-head overview-head">
        <div>
          <span className="eyebrow">{team.manager_name ? `${team.manager_name} · ` : ""}Team {team.team_id}</span>
          <h1>{team.name}</h1>
        </div>
        {showToggle ? (
          <Segmented<View>
            label="Overview mode"
            value={activeView}
            onChange={setView}
            options={[
              { value: "live", label: `GW${state.currentEvent} live` },
              { value: "plan", label: `GW${state.targetEvent} plan` },
            ]}
          />
        ) : null}
      </header>

      {error ? <DataState tone="warning" compact title="Latest refresh failed">Showing the last successful data. {error}</DataState> : null}

      {activeView === "live" && canShowLive && live ? (
        <LiveCockpit live={live} squad={squad} source={liveSource(state)} overallRank={team.overall_rank ?? null} eventRank={team.event_rank ?? null} />
      ) : (
        <>
          {plan ? (
            <GameweekPlanCard plan={plan} event={state.targetEvent} modelVersion={state.modelVersion} locked={!state.actionsOpen} />
          ) : (
            <DataState tone="unavailable" title="No model plan right now">
              {state.failedAreas.has("decision")
                ? "The decision engine could not produce a plan for this team. Official team data below is still current."
                : "A plan appears here once model projections exist for the next Gameweek."}
            </DataState>
          )}
          {plan && !state.actionsOpen && !state.liveActive ? (
            <DataState tone="stale" compact title="This plan is past its deadline">
              The latest model projections target GW{state.targetEvent}, whose deadline has passed. Treat it as context, not advice, until the model is refreshed for the next Gameweek.
            </DataState>
          ) : null}

          <div className="overview-grid">
            <Card title="Best XI" eyebrow="Model lineup from your squad" icon={<Shirt size={16} />} source="model" action={<Link className="link" href="/team">Edit lineup <ArrowRight size={13} aria-hidden="true" /></Link>} className="overview-pitch">
              {plan?.modelXI.length === 11 ? (
                <>
                  <PitchSurface compact label="Model starting eleven with projected points">
                    <FormationRows starters={plan.modelXI} render={(player) => <PitchPlayer key={player.id} player={{ ...player, isStarter: true }} mode="projected" size="sm" captainId={plan.captain?.id} viceId={plan.vice?.id} />} />
                  </PitchSurface>
                  <div className="bench bench-compact">
                    <div className="bench-head"><span className="eyebrow">Bench order</span></div>
                    <div className="bench-row">{plan.bench.map((player, index) => <PitchPlayer key={player.id} player={{ ...player, isStarter: false }} mode="projected" size="sm" benchIndex={index} captainId={-1} viceId={-1} />)}</div>
                  </div>
                </>
              ) : (
                <DataState compact tone="unavailable" title="Model lineup unavailable">Open My Team to see your official XI.</DataState>
              )}
            </Card>

            <div className="overview-side">
              {change ? (
                <Card title="What changed" icon={<History size={16} />} source="derived" tone="warn">
                  <p className="change-line"><s>{change.previous.action}</s><ArrowRight size={14} aria-hidden="true" /><b>{change.current.action}</b></p>
                  <ul className="change-reasons">{change.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
                  <p className="card-note">Compared with the plan last seen in this browser on {new Date(change.previous.recordedAt).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}.</p>
                </Card>
              ) : null}

              <Card title="Season" icon={<LineChart size={16} />} source={officialSource(state)} action={<Link className="link" href="/review">History</Link>}>
                <div className="season-stats">
                  <Stat size="sm" label="Overall rank" value={compact(team.overall_rank)} />
                  <Stat size="sm" label={lastGw ? `GW${lastGw.event} points` : "GW points"} value={integer(lastGw?.points ?? team.event_points)} />
                  <Stat size="sm" label="Total" value={integer(team.total_points)} />
                  <Stat size="sm" label="Value · bank" value={price(team.value)} sub={`${price(team.bank)} in the bank`} />
                </div>
                {history.filter((item) => item.overall_rank).length > 1 ? (
                  <TrendChart
                    label="Overall rank by Gameweek; lower is better"
                    points={history.filter((item) => item.overall_rank).map((item) => ({ x: item.event, y: item.overall_rank as number }))}
                    invert
                    height={130}
                    yLabel={(value) => compact(value)}
                  />
                ) : <p className="faint">Rank trend appears after two Gameweeks.</p>}
                {history.length > 1 ? <p className="card-note">Rank {(() => {
                  const ranked = history.filter((item) => item.overall_rank);
                  if (ranked.length < 2) return "trend pending";
                  const moved = (ranked[0].overall_rank ?? 0) - (ranked[ranked.length - 1].overall_rank ?? 0);
                  return moved >= 0 ? `up ${compact(moved)} places since GW${ranked[0].event}` : `down ${compact(-moved)} places since GW${ranked[0].event}`;
                })()}.</p> : null}
              </Card>

              {state.liveActive && live && activeView !== "live" ? (
                <Card title={`GW${live.event} is live`} source={liveSource(state)} tone="live">
                  <p className="row"><strong className="num live-mini">{live.points ?? "—"}</strong><span className="muted">live points · {live.playing} playing · {live.remaining} to play</span></p>
                  <button type="button" className="link" onClick={() => setView("live")}>Open live cockpit <ArrowRight size={13} aria-hidden="true" /></button>
                </Card>
              ) : null}
            </div>
          </div>

          <SquadFixtures squad={squad} />

          {plan?.recommended && plan.alternatives.length ? (
            <p className="overview-footnote faint">
              {plan.alternatives.length} alternative plan{plan.alternatives.length === 1 ? "" : "s"} evaluated · best alternative 5-GW net {signed(plan.alternatives[0].horizonNet)} xP. <Link className="link" href="/plan#compare">Compare all</Link> <SourceBadge kind="derived" />
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
