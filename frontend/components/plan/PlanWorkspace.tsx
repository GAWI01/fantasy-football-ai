"use client";

import { Crown, GitCompareArrows, Grid3x3, History, Info, Lightbulb, Repeat2, Zap } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Kit } from "@/components/kit/Kit";
import { clubCode } from "@/lib/fpl/kits";
import { MoveRow, ProvisionalPill, ScenarioMetrics } from "@/components/overview/GameweekPlanCard";
import { useTeam } from "@/app/providers/TeamProvider";
import { ChipSquadSheet, type ChipSquadKind } from "@/components/plan/ChipSquadSheet";
import { FreeTransfersControl } from "@/components/plan/FreeTransfersControl";
import { OwnMoveCard } from "@/components/plan/OwnMoveCard";
import { PriceTiming } from "@/components/prices/PriceTiming";
import { NextWeekLine, TwoWeekCard } from "@/components/plan/TwoWeekPlan";
import { ExplainPlan } from "@/components/plan/WhySheet";
import { PlayerChip } from "@/components/player/PlayerChip";
import { PageSectionTabs } from "@/components/shell/PageTabs";
import { Term } from "@/components/ui/Term";
import { DataState } from "@/components/states/DataState";
import { Card, Delta, Meter, SourceBadge } from "@/components/ui/primitives";
import { fixed, price, sentenceCase, signed } from "@/lib/format";
import { useCockpit } from "@/lib/hooks/useCockpit";
import { usePlanHistory } from "@/lib/hooks/usePlanHistory";
import { chipAvailability, CHIP_LABEL, planSnapshot, transferHeadline, type GameweekPlan, type ScenarioView } from "@/lib/model/plan";
import type { SquadPlayer } from "@/lib/model/squad";
import type { ChipOutlook } from "@/lib/contracts";

/** One sentence a newcomer can read: what the move is worth, in points. */
function plainSummary(plan: GameweekPlan, scenario: ScenarioView, adopted: boolean): string {
  const next = scenario.nextGwGain;
  const total = scenario.horizonNet ?? scenario.horizonGain;
  const weeks = plan.horizon ?? 5;
  const worth = [
    next != null ? `${signed(next)} points next Gameweek` : null,
    total != null ? `${signed(total)} over the next ${weeks} Gameweeks` : null,
  ].filter(Boolean).join(" and ");
  if (!worth) return adopted ? "The model expects this to gain points." : "The best swap found does not gain enough.";
  if (adopted) return `Expected to add about ${worth}${scenario.hit ? `, after the −${scenario.hit} hit` : ""}.`;
  return `The best swap found would add about ${worth}: not enough to beat saving the transfer.`;
}

function scenarioTitle(scenario: ScenarioView): string {
  if (!scenario.moves.length) return "Hold · roll the transfer";
  return scenario.moves.map((move) => `${move.outName} → ${move.inName}`).join(", ");
}

/** "+12.9 gain − 4 hit − 2.0 margin − 2.0 banked transfer = +4.9" */
function scoreMath(row: ScenarioView): string {
  const hit = row.hit ?? 0;
  const margin = Math.max(0, (row.weightedNet ?? row.weightedGain - hit) - row.rollValue - row.modelScore);
  const parts = [`${signed(row.weightedGain)} weighted gain`];
  if (hit) parts.push(`− ${hit} hit`);
  if (margin > 0.05) parts.push(`− ${fixed(margin)} margin`);
  if (row.rollValue > 0.05) parts.push(`− ${fixed(row.rollValue)} banked transfer`);
  return `${parts.join(" ")} = ${signed(row.modelScore)}`;
}

function ScenarioCompare({ plan }: { plan: GameweekPlan }) {
  const rows = useMemo(() => {
    const list: ScenarioView[] = [plan.hold];
    const primary = plan.verdict === "TRANSFER" ? plan.recommended : plan.bestRejected;
    if (primary) list.push(primary);
    for (const alternative of plan.alternatives) {
      if (!list.some((row) => scenarioTitle(row) === scenarioTitle(alternative))) list.push(alternative);
    }
    // Sort the single-stage scores; conservative two-stage selection may recommend a lower row.
    return list.sort((left, right) => right.modelScore - left.modelScore);
  }, [plan]);
  const recommendedTitle = scenarioTitle(plan.verdict === "TRANSFER" ? plan.recommended : plan.hold);
  const [selected, setSelected] = useState(recommendedTitle);
  const active = rows.find((row) => scenarioTitle(row) === selected) ?? rows[0];
  const noHit = rows.find((row) => row.moves.length && row.hit === 0);
  const withHit = rows.find((row) => (row.hit ?? 0) > 0);

  return (
    <Card id="compare" title="Other options" eyebrow="What else was considered" icon={<GitCompareArrows size={16} />} source={["model", "derived"]}
      collapse={{ id: "plan-compare", defaults: { mobile: false, desktop: true }, summary: `${rows.length} options ranked · tap to compare` }}>
      <div className="scenarios" role="radiogroup" aria-label="Transfer scenarios">
        <div className="scenario scenario-head" aria-hidden="true">
          <span>Option</span><span>Next GW</span><span>{plan.horizon ?? "Multi"}-GW projected net</span><span>Hit</span><span>Decision score</span>
        </div>
        {rows.map((row) => {
          const title = scenarioTitle(row);
          const isRecommended = title === recommendedTitle;
          return (
            <button
              type="button"
              role="radio"
              aria-checked={title === selected}
              key={title}
              className={`scenario${isRecommended ? " is-recommended" : ""}`}
              onClick={() => setSelected(title)}
            >
              <span className="scenario-title">
                {isRecommended ? <span className="pill pill-accent">Recommended</span> : null}
                <b>{title}</b>
                {row.moves.length ? <small className="scenario-math">{scoreMath(row)}</small> : <small className="scenario-math">Baseline: keeps the free transfer for later</small>}
              </span>
              <span data-label="Next GW"><Delta value={row.nextGwGain} /></span>
              <span data-label={`${plan.horizon ?? "Multi"}-GW projected net`}>{row.horizonNet == null ? "Unavailable" : <Delta value={row.horizonNet} />}</span>
              <span data-label="Hit" className={row.hit ? "tone-neg" : "faint"}>{row.hit == null ? "?" : row.hit ? `−${row.hit}` : "0"}</span>
              <span data-label="Decision score" className="scenario-score"><Delta value={row.modelScore} /></span>
            </button>
          );
        })}
      </div>
      {/* The recommended option is already spelled out in the transfer decision. */}
      {active && scenarioTitle(active) !== recommendedTitle ? (
        <div className="scenario-detail">
          <span className="eyebrow">Selected: {scenarioTitle(active)}</span>
          {active.moves.length ? active.moves.map((move) => <MoveRow key={`${move.outId}-${move.inId}`} move={move} />) : <p className="muted">Keep the squad and carry the free transfer. Nothing changes this Gameweek, and you keep flexibility for team news.</p>}
          <ScenarioMetrics scenario={active} plan={plan} />
        </div>
      ) : rows.length > 1 ? <p className="card-note">Tap another option to see its moves next to the recommendation.</p> : null}
      {withHit ? (
        <p className="card-note">
          <b>Hit check:</b> highest-scoring evaluated hit option projects {withHit.horizonNet == null ? "unavailable net points" : `${signed(withHit.horizonNet)} xP after hits`} over {plan.horizon ?? "the available"} Gameweeks{noHit ? `, versus ${noHit.horizonNet == null ? "unavailable net points" : `${signed(noHit.horizonNet)} xP`} for the highest-scoring free move` : ""}. {plan.recommended.hit ? "The engine accepts this hit." : "The engine does not take the hit."}
        </p>
      ) : null}
      <details className="card-more">
        <summary>How is the score worked out?</summary>
        <p className="card-note">
        <b>Decision score</b> uses the weighted {plan.horizon ?? "multi"}-Gameweek gain (later weeks count less), minus any hit, minus a safety margin per hit,
        minus what the free transfers it uses would be worth if you banked them. Holding scores 0 in this single-stage comparison. The conservative policy may recommend an option with a lower single-stage score when next-week follow-ups favor fewer moves now. Projected net points use unweighted forecasts after actual hits; safety margins and roll values are policy values.
        See the <a href="#why">Why</a> tab for more.
        </p>
      </details>
    </Card>
  );
}

function CaptainCompare({ plan, squad }: { plan: GameweekPlan; squad: SquadPlayer[] }) {
  const options = plan.captainOptions.length ? plan.captainOptions : squad.filter((player) => player.isStarter && player.xp != null).sort((left, right) => (right.xp ?? 0) - (left.xp ?? 0)).slice(0, 5).map((player) => ({ player, captainScore: null }));
  const [pick, setPick] = useState<number | null>(null);
  const active = options.find((option) => option.player.id === pick)?.player ?? plan.captain;
  const max = Math.max(1, ...options.map((option) => option.player.xp ?? 0));
  const delta = active?.xp != null && plan.captain?.xp != null ? active.xp - plan.captain.xp : null;
  return (
    <Card title="Captaincy" eyebrow={plan.lineupAfterTransfers ? "Your squad after the plan" : "Owned players only"} icon={<Crown size={16} />} source="model">
      <div className="cap-list" role="radiogroup" aria-label="Captain options">
        {options.map(({ player, captainScore }) => (
          <button type="button" role="radio" aria-checked={active?.id === player.id} key={player.id} className={`cap-row${plan.captain?.id === player.id ? " is-recommended" : ""}`} onClick={() => setPick(player.id)}>
            <PlayerChip name={player.name} team={player.team} teamShort={player.teamShort} position={player.position} size={30} badge={plan.captain?.id === player.id ? "C" : plan.vice?.id === player.id ? "V" : undefined} meta={`${player.opponent ?? "Fixture —"}${player.home == null ? "" : player.home ? " (H)" : " (A)"} · ${player.xmins == null ? "—" : Math.round(player.xmins)} xMins`} />
            <span className="cap-bar" aria-hidden="true"><i style={{ width: `${((player.xp ?? 0) / max) * 100}%` }} /></span>
            <span className="cap-xp num"><b>{fixed(player.xp)}</b><small>{captainScore != null ? `score ${fixed(captainScore, 2)}` : "xP"}</small></span>
          </button>
        ))}
      </div>
      {active && plan.captain && active.id !== plan.captain.id ? (
        <p className="card-note">Captaining <b>{active.name}</b> instead of {plan.captain.name}: <Delta value={delta} unit=" xP" /> expected from the armband. <SourceBadge kind="derived" /></p>
      ) : <p className="card-note">{plan.lineupAfterTransfers ? "Chosen from your squad after the recommended transfers" : "Chosen from your owned players"}: the highest projected points (minutes and availability are already in the projection). Vice: <b>{plan.vice?.name ?? "—"}</b>.</p>}
    </Card>
  );
}

/** Each chip you still have: play it now or save it, and the week that suits it best. */
function ChipOutlookList({ outlook }: { outlook: ChipOutlook[] }) {
  const available = outlook.filter((item) => item.available);
  const used = outlook.filter((item) => !item.available);
  return (
    <div className="chip-outlook">
      {available.map((item) => (
        <div key={item.chip} className={`chip-row chip-row-${item.verdict === "USE" ? "use" : "save"}`}>
          <div className="chip-row-head">
            <b>{item.label}</b>
            <span className={`pill ${item.verdict === "USE" ? "pill-warn" : ""}`}>{item.verdict === "USE" ? "Play now" : "Save"}</span>
            {item.best_window && item.verdict !== "USE" ? <span className="pill pill-accent">Best: GW{item.best_window.gameweek}</span> : null}
          </div>
          {item.summary ? <p>{item.summary}</p> : null}
          {item.this_week != null && item.threshold != null ? (
            <div className="chip-meter">
              <Meter value={Math.min(1, item.this_week / item.threshold)} label={`${item.label} this week`} tone={item.this_week >= item.threshold ? "pos" : "warn"} />
              <small className="faint">This week {fixed(item.this_week)} · worth it from {fixed(item.threshold)}</small>
            </div>
          ) : null}
        </div>
      ))}
      {!available.length ? <p className="muted">You have no chips left this half of the season.</p> : null}
      {used.length ? <p className="card-note">Used this half: {used.map((item) => item.label).join(", ")}.</p> : null}
    </div>
  );
}

function ChipCard({ plan, locked }: { plan: GameweekPlan; locked: boolean }) {
  const chips = chipAvailability(plan.chip.state);
  const state = plan.chip.state;
  const { teamId } = useTeam();
  const [squadSheet, setSquadSheet] = useState<ChipSquadKind | null>(null);
  const [squadKind, setSquadKind] = useState<ChipSquadKind>("free_hit");
  const statusOf = (chip: string) => chips.find((item) => item.chip === chip)?.status ?? "unknown";
  return (
    <Card id="chips" title="Chips" icon={<Zap size={16} />} source={["model", "official"]}>
      <div className="chip-call">
        <span className="eyebrow">{locked ? "Locked for this deadline" : "Recommendation"}</span>
        <strong className={plan.chip.recommended ? "tone-warn" : undefined}>{plan.chip.recommended ? `Play ${CHIP_LABEL[plan.chip.recommended]}` : "Hold your chips"}</strong>
        <p className="muted">{plan.chip.recommended ? `${plan.chip.reason ?? `The ${CHIP_LABEL[plan.chip.recommended]} case beats its evidence bar.`} Check team news before committing.` : "No chip is worth playing this week. Each chip below shows what it needs and the week in view that suits it best."}</p>
        {plan.chipBudgetIsEstimate ? <p className="card-note">Chip squad affordability is estimated from market prices. Check your actual selling prices in FPL.</p> : null}
      </div>
      {plan.chip.outlook.length ? <ChipOutlookList outlook={plan.chip.outlook} /> : (
        <div className="chip-grid">
          {chips.map((chip) => (
            <span key={chip.chip} className={`chip-pill chip-${chip.status}`}>
              <b>{chip.label}</b>
              <small>{chip.status === "available" ? "Available" : chip.status === "used" ? "Used this half" : "Unknown"}</small>
            </span>
          ))}
        </div>
      )}
      <div className="chip-squad-actions">
        <button type="button" className="btn btn-sm" onClick={() => { setSquadKind("free_hit"); setSquadSheet("free_hit"); }}>Best Free Hit team</button>
        <button type="button" className="btn btn-sm" onClick={() => { setSquadKind("wildcard"); setSquadSheet("wildcard"); }}>Best Wildcard team</button>
      </div>
      <ChipSquadSheet open={squadSheet != null} onClose={() => setSquadSheet(null)} kind={squadKind} onKind={setSquadKind} teamId={teamId}
        chipStatus={{ free_hit: statusOf("FREE_HIT"), wildcard: statusOf("WILDCARD") }} />
      {state ? (
        <p className="card-note">
          {state.double_gameweek ? "Double Gameweek fixtures exist in the target Gameweek. " : ""}
          {state.blank_gameweek ? "Some clubs blank in the target Gameweek. " : ""}
          {!state.double_gameweek && !state.blank_gameweek ? "Normal Gameweek: every club plays once. " : ""}
          {state.known ? "Availability comes from your official chip history." : "Chip history could not be read, so availability is unknown."}
        </p>
      ) : null}
    </Card>
  );
}

function HorizonGrid({ squad }: { squad: SquadPlayer[] }) {
  const gameweeks = [...new Set(squad.flatMap((player) => player.horizon.map((gameweek) => gameweek.gameweek)))].sort((left, right) => left - right);
  if (!gameweeks.length) return <DataState compact tone="unavailable" title="Five-Gameweek horizon unavailable">The model did not return multi-Gameweek projections.</DataState>;
  const max = Math.max(1, ...squad.flatMap((player) => player.horizon.map((gameweek) => gameweek.predicted_points)));
  const sorted = [...squad].sort((left, right) => (right.horizonTotal ?? 0) - (left.horizonTotal ?? 0));
  return (
    <Card title="Squad outlook" eyebrow={`GW${gameweeks[0]}–${gameweeks[gameweeks.length - 1]} projected points`} icon={<Grid3x3 size={16} />} source="model">
      <div className="heat-wrap">
        <table className="heat">
          <thead>
            <tr><th scope="col">Player</th>{gameweeks.map((gameweek) => <th scope="col" key={gameweek}>GW{gameweek}</th>)}<th scope="col" className="num">Total</th></tr>
          </thead>
          <tbody>
            {sorted.map((player) => (
              <tr key={player.id} className={player.isStarter ? undefined : "is-bench"}>
                <th scope="row"><span className="heat-player"><Kit team={player.team} teamShort={player.teamShort} goalkeeper={player.position === "GKP"} size={22} bare /><span>{player.name}<small>{player.position}{player.isStarter ? "" : " · bench"}</small></span></span></th>
                {gameweeks.map((gameweek) => {
                  const cell = player.horizon.find((item) => item.gameweek === gameweek);
                  if (!cell) return <td key={gameweek} className="heat-cell heat-empty">—</td>;
                  const blank = cell.fixture_count === 0;
                  const intensity = blank ? 0 : cell.predicted_points / max;
                  return (
                    <td key={gameweek} className={`heat-cell${blank ? " heat-blank" : ""}`} style={{ ["--heat" as string]: intensity.toFixed(3) }} title={`${player.name} GW${gameweek}: ${blank ? "blank" : `${cell.opponent ?? "TBC"}${cell.home == null ? "" : cell.home ? " (H)" : " (A)"}`} · ${fixed(cell.predicted_points)} xP`}>
                      <b>{blank ? "—" : fixed(cell.predicted_points)}</b>
                      <small>{blank ? "Blank" : `${cell.opponent ? clubCode(cell.opponent) : "TBC"}${cell.home == null ? "" : cell.home ? " H" : " A"}`}</small>
                    </td>
                  );
                })}
                <td className="num heat-total"><b>{fixed(player.horizonTotal)}</b></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="card-note">Darker cells mean more expected points. Bench players are dimmed.</p>
    </Card>
  );
}

function RiskCard({ squad }: { squad: SquadPlayer[] }) {
  const risky = squad.filter((player) => player.risk).sort((left, right) => (right.risk?.score ?? 0) - (left.risk?.score ?? 0)).slice(0, 5);
  return (
    <Card title="Minutes risk" icon={<Info size={16} />} source="model">
      {risky.length ? (
        <div className="list">
          {risky.map((player) => (
            <div className="list-row" key={player.id}>
              <PlayerChip name={player.name} team={player.team} teamShort={player.teamShort} position={player.position} size={28} meta={`${player.isStarter ? "Starter" : "Bench"} · ${sentenceCase(player.risk?.label)}`} />
              <span className="risk-meter"><Meter value={player.risk?.score} label={`${player.name} risk`} tone={(player.risk?.score ?? 0) >= 0.45 ? "neg" : (player.risk?.score ?? 0) >= 0.2 ? "warn" : "pos"} /></span>
            </div>
          ))}
        </div>
      ) : <p className="faint">Risk model unavailable.</p>}
    </Card>
  );
}

type PlanTab = "transfers" | "captain" | "chips" | "squad" | "why";

// Old links (#compare, #why …) still land on the section that holds them.
const HASH_TAB: Record<string, PlanTab> = {
  transfers: "transfers", compare: "transfers", "two-week": "transfers", "test-move": "transfers",
  captain: "captain", chips: "chips", squad: "squad", risk: "squad", why: "why", history: "why",
};

/** The Plan's open section, kept in the address (#chips) so links and the back button work. */
function usePlanTab(): [PlanTab, (tab: PlanTab) => void] {
  const [tab, setTabState] = useState<PlanTab>("transfers");
  useEffect(() => {
    const sync = () => {
      const hash = window.location.hash.slice(1);
      const next = HASH_TAB[hash];
      if (!next) return;
      setTabState(next);
      // A deep link to a card inside the section (#compare) scrolls to it once it renders.
      if (hash !== next) window.setTimeout(() => document.getElementById(hash)?.scrollIntoView({ block: "start" }), 50);
    };
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  const setTab = useCallback((next: PlanTab) => {
    setTabState(next);
    window.history.replaceState(null, "", `#${next}`);
  }, []);
  return [tab, setTab];
}

export function PlanWorkspace() {
  const { ready, teamId, dashboard, loading, error, refresh, state, squad, plan, market, marketLoading } = useCockpit();
  const snapshot = useMemo(
    () => (plan && state.actionsOpen && dashboard ? planSnapshot(plan, state.targetEvent, state.modelVersion, dashboard.meta.generated_at) : null),
    [plan, state.actionsOpen, state.targetEvent, state.modelVersion, dashboard],
  );
  const { history, change } = usePlanHistory(snapshot, teamId);
  const [tab, setTab] = usePlanTab();

  if (!ready || (!dashboard && loading)) return <DataState title="Loading your plan" loading>Running the decision engine on your squad.</DataState>;
  if (!dashboard && error) return <DataState tone="error" title="Your plan could not be loaded" action={<button className="btn btn-sm btn-primary" onClick={() => void refresh()}>Try again</button>}>{error}</DataState>;
  if (!dashboard) return <DataState tone="empty" title="Connect a team to build a plan" action={<Link className="btn btn-sm btn-primary" href="/">Connect your team</Link>}>Plans use your squad, bank, free transfers and chip history.</DataState>;
  if (!plan) {
    return (
      <div>
        <header className="page-head"><div><span className="eyebrow">Plan & Transfers</span><h1>No plan available</h1></div></header>
        {error ? <DataState tone="error" compact title="Refresh failed">{error} Showing the last loaded data.</DataState> : null}
        <DataState tone="unavailable" title="The decision engine returned no plan">Official team data is still available on My Team. Try refreshing; if model projections are missing for the next Gameweek, the plan appears once they are published.</DataState>
      </div>
    );
  }

  const locked = !state.actionsOpen;
  const isTransfer = plan.verdict === "TRANSFER";
  return (
    <div className="plan-page">
      <header className="page-head">
        <div>
          <span className="eyebrow">Plan & Transfers · Gameweek {state.targetEvent ?? "—"}</span>
          <h1>{isTransfer ? transferHeadline(plan) : "Hold this week"}</h1>
          <p>{isTransfer ? "Our pick for this Gameweek. It weighs points over the coming weeks against hits and the value of keeping your free transfer." : "Nothing clearly beats your current squad, so save the free transfer for next week."}</p>
        </div>
        <div className="page-head-actions">
          {plan.confidence ? <span className={`pill ${plan.confidence.label === "HIGH" ? "pill-pos" : plan.confidence.label === "LOW" ? "pill-warn" : "pill-accent"}`}><Term k="confidence">{sentenceCase(plan.confidence.label)} confidence</Term></span> : null}
          <span className="pill">Bank {price(plan.bank)}</span>
          {state.forecastProvisional && state.historyCutoff != null ? <ProvisionalPill cutoff={state.historyCutoff} event={state.targetEvent} /> : null}
        </div>
      </header>

      {error ? <DataState tone="error" compact title="Refresh failed" action={<button className="btn btn-sm" onClick={() => void refresh()}>Try again</button>}>{error} Showing the last loaded plan.</DataState> : null}
      {locked ? <DataState tone="stale" compact title={state.liveActive ? "Gameweek in progress" : "Deadline passed"}>These recommendations target GW{state.targetEvent}, whose deadline has passed. They are shown for context and cannot be acted on.</DataState> : null}
      {marketLoading ? <p className="faint loading-note">Loading incoming-player projections…</p> : null}

      <PageSectionTabs<PlanTab>
        label="Plan sections"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "transfers", label: "Transfers" },
          { value: "captain", label: "Captain" },
          { value: "chips", label: <>Chips{plan.chip.recommended ? <i className="tab-dot" aria-label="a chip is recommended" /> : null}</> },
          { value: "squad", label: "Squad" },
          { value: "why", label: "Why" },
        ]}
      />

      <div className="plan-grid" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "transfers" ? (
          <>
            <Card id="transfers" title={isTransfer ? "Our pick" : "Our pick: save the transfer"} icon={<Repeat2 size={16} />} source={(isTransfer ? plan.recommended : plan.bestRejected) ? ["model", "derived"] : "model"} tone={isTransfer ? "accent" : undefined} className="plan-transfer">
              <div className="verdict verdict-inline">
                {isTransfer ? plan.recommended.moves.map((move) => <MoveRow key={`${move.outId}-${move.inId}`} move={move} />) : plan.bestRejected ? (
                  <div className="rejected"><span className="eyebrow">Evaluated move · conservative policy recommends holding</span>{plan.bestRejected.moves.map((move) => <MoveRow key={`${move.outId}-${move.inId}`} move={move} compact />)}</div>
                ) : <p className="muted">No transfer alternative was returned.</p>}
                {(isTransfer ? plan.recommended : plan.bestRejected) ? (
                  <>
                    <p className="plain-summary">{plainSummary(plan, isTransfer ? plan.recommended : plan.bestRejected!, isTransfer)}</p>
                    <FreeTransfersControl count={plan.freeTransfers} source={plan.freeTransfersSource} />
                    <details className="card-more">
                      <summary>See the numbers</summary>
                      <ScenarioMetrics scenario={isTransfer ? plan.recommended : plan.bestRejected!} plan={plan} showFreeTransfers={false} />
                    </details>
                  </>
                ) : null}
                {isTransfer && !locked ? <PriceTiming moves={plan.recommended.moves} /> : null}
                <NextWeekLine plan={plan.twoWeek} transfersNow={isTransfer ? plan.recommended.moves.length : 0} />
              </div>
            </Card>
            <div className="plan-wide"><ScenarioCompare plan={plan} /></div>
            {plan.twoWeek ? <TwoWeekCard plan={plan.twoWeek} transfersNow={isTransfer ? plan.recommended.moves.length : 0} /> : null}
            {teamId && !locked ? <OwnMoveCard teamId={teamId} plan={plan} squad={squad} market={market} /> : null}
          </>
        ) : null}
        {tab === "captain" ? <div className="plan-wide"><CaptainCompare plan={plan} squad={squad} /></div> : null}
        {tab === "chips" ? <div className="plan-wide"><ChipCard plan={plan} locked={locked} /></div> : null}
        {tab === "squad" ? (
          <>
            <div className="plan-wide"><HorizonGrid squad={squad} /></div>
            <RiskCard squad={squad} />
          </>
        ) : null}
        {tab === "why" ? (
          <>
            <Card id="why" title="Why this plan" icon={<Lightbulb size={16} />} className="plan-why">
              <ExplainPlan plan={plan} modelVersion={state.modelVersion} />
            </Card>
            <Card id="history" title="Plan history" icon={<History size={16} />} source="derived">
              {change ? <p className="change-line"><s>{change.previous.action}</s> → <b>{change.current.action}</b></p> : null}
              {history.length ? (
                <ol className="history-list">
                  {history.map((item, index) => (
                    <li key={`${item.recordedAt}-${item.action}`}>
                      <span className="faint">GW{item.event}</span>
                      <span><b>{item.action}</b><small>Captain {item.captain}</small></span>
                      <span className="faint">{index === 0 ? "Now" : new Date(item.recordedAt).toLocaleDateString([], { day: "numeric", month: "short" })}</span>
                    </li>
                  ))}
                </ol>
              ) : <p className="faint">Plans are remembered in this browser when the recommendation changes meaningfully.</p>}
            </Card>
          </>
        ) : null}
      </div>
    </div>
  );
}
