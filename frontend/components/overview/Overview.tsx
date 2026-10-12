"use client";

import { ArrowRight, History, LineChart, Shirt, Zap } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { TrendChart } from "@/components/charts/TrendChart";
import { SquadFixtures } from "@/components/fixtures/SquadFixtures";
import { ConnectHero } from "@/components/overview/ConnectHero";
import { chipSummary, GameweekPlanCard, PlanChipDetails, PlanLineupDetails } from "@/components/overview/GameweekPlanCard";
import { LiveCockpit } from "@/components/overview/LiveCockpit";
import { FormationRows, PitchPlayer, PitchSurface } from "@/components/pitch/Pitch";
import { DataState } from "@/components/states/DataState";
import { CountUp } from "@/components/ui/CountUp";
import { Card, Segmented, SourceBadge, Stat } from "@/components/ui/primitives";
import { compact, fixed, integer, price, signed } from "@/lib/format";
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
  // After the last match the Gameweek's result stays one tap away; the plan leads.
  const canShowLive = (state.liveActive || state.gwPlayed) && live != null;
  const canShowPlan = plan != null;
  const activeView: View = view ?? (canShowLive && state.liveActive ? "live" : canShowPlan ? "plan" : canShowLive ? "live" : "plan");
  const showToggle = canShowLive && canShowPlan && state.actionsOpen;
  const lastGw = history[history.length - 1];

  return (
    <div className="overview">
      <header className="page-head overview-head">
        <div>
          <span className="eyebrow">Team {team.team_id}</span>
          <h1>{team.name}</h1>
        </div>
        {showToggle ? (
          <Segmented<View>
            label="Overview mode"
            value={activeView}
            onChange={setView}
            options={[
              { value: "live", label: `GW${state.currentEvent} ${state.gwPlayed ? "result" : "live"}` },
              { value: "plan", label: `GW${state.targetEvent} plan` },
            ]}
          />
        ) : null}
      </header>

      {error ? <DataState tone="warning" compact title="Latest refresh failed">Showing the last successful data. {error}</DataState> : null}

      {activeView === "live" && canShowLive && live ? (
        <LiveCockpit
          live={live}
          squad={squad}
          source={liveSource(state)}
          overallRank={team.overall_rank ?? null}
          eventRank={team.event_rank ?? null}
          gwPlayed={state.gwPlayed}
          planPreview={showToggle && plan ? {
            event: state.targetEvent,
            label: plan.verdict === "TRANSFER" ? plan.recommended.moves.map((move) => `${move.outName} → ${move.inName}`).join(", ") : "Hold the transfer",
            provisional: state.forecastProvisional,
            onOpen: () => setView("plan"),
          } : null}
        />
      ) : (
        <>
          {state.liveActive && live ? (
            <button type="button" className="preview-line preview-live" onClick={() => setView("live")}>
              <i className="preview-dot" aria-hidden="true" />
              <span><b>GW{live.event} live</b> · {live.points ?? "—"} pts · {live.playing} playing · {live.remaining} to play</span>
              <span className="preview-cta">Open live<ArrowRight size={14} aria-hidden="true" /></span>
            </button>
          ) : state.gwPlayed && live ? (
            <button type="button" className="preview-line preview-result" onClick={() => setView("live")}>
              <span><b>GW{live.event} result</b> · {live.points ?? "—"} pts · full time</span>
              <span className="preview-cta">Open result<ArrowRight size={14} aria-hidden="true" /></span>
            </button>
          ) : null}
          {plan ? (
            <GameweekPlanCard plan={plan} event={state.targetEvent} modelVersion={state.modelVersion} locked={!state.actionsOpen} provisionalCutoff={state.forecastProvisional ? state.historyCutoff : null} />
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
            <Card
              title="Lineup & captain"
              eyebrow={plan?.lineupAfterTransfers ? "Model lineup after the recommended transfers" : "Model lineup from your squad"}
              icon={<Shirt size={16} />}
              source="model"
              action={<Link className="link" href="/team">Edit lineup <ArrowRight size={13} aria-hidden="true" /></Link>}
              className="overview-pitch"
              collapse={{
                id: "lineup",
                defaults: { mobile: false, desktop: true },
                summary: plan?.captain ? `Captain ${plan.captain.name} · ${fixed(plan.projectedScore)} xP${plan.formation ? ` · ${plan.formation}` : ""}` : "Model lineup",
              }}
            >
              {plan ? <PlanLineupDetails plan={plan} /> : null}
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
                <Card
                  title="What changed"
                  icon={<History size={16} />}
                  source="derived"
                  tone="warn"
                  collapse={{
                    id: "changed",
                    defaults: { mobile: false, desktop: true },
                    summary: `${change.previous.action} → ${change.current.action}`,
                    // A new change opens the section on every screen until it is closed.
                    signal: `change:${change.previous.recordedAt}:${change.current.action}`,
                  }}
                >
                  <p className="change-line"><s>{change.previous.action}</s><ArrowRight size={14} aria-hidden="true" /><b>{change.current.action}</b></p>
                  <ul className="change-reasons">{change.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
                  <p className="card-note">Compared with the plan last seen in this browser on {new Date(change.previous.recordedAt).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}.</p>
                </Card>
              ) : null}

              {plan ? (
                <Card
                  title="Chip"
                  icon={<Zap size={16} />}
                  source={["model", "official"]}
                  action={<Link className="link" href="/plan#chips">Outlook</Link>}
                  collapse={{
                    id: "chip",
                    defaults: { mobile: false, desktop: false },
                    summary: chipSummary(plan),
                    signal: plan.chip.recommended ? `chip:${state.targetEvent}:${plan.chip.recommended}` : null,
                  }}
                >
                  <PlanChipDetails plan={plan} />
                </Card>
              ) : null}

              <Card
                title="Season"
                icon={<LineChart size={16} />}
                source={officialSource(state)}
                action={<Link className="link" href="/review">History</Link>}
                collapse={{
                  id: "season",
                  defaults: { mobile: false, desktop: true },
                  summary: `Overall rank ${compact(team.overall_rank)} · ${lastGw ? `GW${lastGw.event} ${integer(lastGw.points)} pts` : `${integer(team.total_points)} pts`}`,
                }}
              >
                <div className="season-stats">
                  <Stat size="sm" label="Overall rank" value={compact(team.overall_rank)} />
                  <Stat size="sm" label={lastGw ? `GW${lastGw.event} points` : "GW points"} value={<CountUp value={lastGw?.points ?? team.event_points} format={(n) => n.toLocaleString("en-GB")} />} />
                  <Stat size="sm" label="Total" value={<CountUp value={team.total_points} format={(n) => n.toLocaleString("en-GB")} />} />
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
            </div>
          </div>

          <SquadFixtures squad={squad} collapse={{ id: "fixtures", defaults: { mobile: false, desktop: true } }} />

          {plan?.recommended && plan.alternatives.length ? (
            <p className="overview-footnote faint">
              {plan.alternatives.length} alternative plan{plan.alternatives.length === 1 ? "" : "s"} evaluated · best alternative {plan.horizon == null ? "horizon" : `${plan.horizon}-GW`} net {signed(plan.alternatives[0].horizonNet)} xP. <Link className="link" href="/plan#compare">Compare all</Link> <SourceBadge kind="derived" />
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
