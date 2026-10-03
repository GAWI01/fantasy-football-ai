"use client";

import { Crown, GitCompareArrows, Grid3x3, History, Info, Lightbulb, Repeat2, Zap } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Kit } from "@/components/kit/Kit";
import { clubCode } from "@/lib/fpl/kits";
import { MoveRow, ScenarioMetrics } from "@/components/overview/GameweekPlanCard";
import { ExplainPlan } from "@/components/plan/WhySheet";
import { PlayerChip } from "@/components/player/PlayerChip";
import { DataState } from "@/components/states/DataState";
import { Card, Delta, Meter, SourceBadge } from "@/components/ui/primitives";
import { fixed, price, sentenceCase, signed } from "@/lib/format";
import { useCockpit } from "@/lib/hooks/useCockpit";
import { usePlanHistory } from "@/lib/hooks/usePlanHistory";
import { chipAvailability, CHIP_LABEL, planSnapshot, transferHeadline, type GameweekPlan, type ScenarioView } from "@/lib/model/plan";
import type { SquadPlayer } from "@/lib/model/squad";

function scenarioTitle(scenario: ScenarioView): string {
  if (!scenario.moves.length) return "Hold · roll the transfer";
  return scenario.moves.map((move) => `${move.outName} → ${move.inName}`).join(", ");
}

function ScenarioCompare({ plan }: { plan: GameweekPlan }) {
  const rows = useMemo(() => {
    const list: ScenarioView[] = [plan.hold];
    const primary = plan.verdict === "TRANSFER" ? plan.recommended : plan.bestRejected;
    if (primary) list.push(primary);
    for (const alternative of plan.alternatives) {
      if (!list.some((row) => scenarioTitle(row) === scenarioTitle(alternative))) list.push(alternative);
    }
    return list;
  }, [plan]);
  const recommendedTitle = scenarioTitle(plan.verdict === "TRANSFER" ? plan.recommended : plan.hold);
  const [selected, setSelected] = useState(recommendedTitle);
  const active = rows.find((row) => scenarioTitle(row) === selected) ?? rows[0];
  const noHit = rows.filter((row) => row.moves.length && row.hit === 0).sort((left, right) => (right.horizonNet ?? -99) - (left.horizonNet ?? -99))[0];
  const withHit = rows.filter((row) => (row.hit ?? 0) > 0).sort((left, right) => (right.horizonNet ?? -99) - (left.horizonNet ?? -99))[0];

  return (
    <Card id="compare" title="Compare options" eyebrow="What-if" icon={<GitCompareArrows size={16} />} source={["model", "derived"]}>
      <div className="scenarios" role="radiogroup" aria-label="Transfer scenarios">
        <div className="scenario scenario-head" aria-hidden="true">
          <span>Option</span><span>Next GW</span><span>5-GW gain</span><span>Hit</span><span>5-GW net</span>
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
              </span>
              <span data-label="Next GW"><Delta value={row.nextGwGain} /></span>
              <span data-label="5-GW gain"><Delta value={row.horizonGain} /></span>
              <span data-label="Hit" className={row.hit ? "tone-neg" : "faint"}>{row.hit == null ? "?" : row.hit ? `−${row.hit}` : "0"}</span>
              <span data-label="5-GW net"><Delta value={row.horizonNet} /></span>
            </button>
          );
        })}
      </div>
      {active ? (
        <div className="scenario-detail">
          <span className="eyebrow">Selected: {scenarioTitle(active)}</span>
          {active.moves.length ? active.moves.map((move) => <MoveRow key={`${move.outId}-${move.inId}`} move={move} />) : <p className="muted">Keep the squad and carry the free transfer. Nothing changes this Gameweek, and you keep flexibility for team news.</p>}
          <ScenarioMetrics scenario={active} freeTransfers={plan.freeTransfers} />
        </div>
      ) : null}
      {withHit ? (
        <p className="card-note">
          <b>Hit check:</b> best plan with a hit nets {signed(withHit.horizonNet)} over five Gameweeks{noHit ? `, versus ${signed(noHit.horizonNet)} for the best free move` : ""}. {plan.recommended.hit ? "The engine accepts this hit." : "The engine does not take the hit."}
        </p>
      ) : null}
      <p className="card-note">Next GW uses each player’s native model projection. 5-GW gain is the model’s minutes-adjusted horizon before hits; 5-GW net subtracts the hit. Options are ranked by the engine’s weighted multi-GW score.</p>
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
    <Card title="Captaincy" eyebrow="Owned players only" icon={<Crown size={16} />} source="model">
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
      ) : <p className="card-note">The model captain balances projected points with minutes security and fixture. Vice: <b>{plan.vice?.name ?? "—"}</b>.</p>}
    </Card>
  );
}

function ChipCard({ plan, locked }: { plan: GameweekPlan; locked: boolean }) {
  const chips = chipAvailability(plan.chip.state);
  const state = plan.chip.state;
  return (
    <Card id="chips" title="Chips" icon={<Zap size={16} />} source={["model", "official"]}>
      <div className="chip-call">
        <span className="eyebrow">{locked ? "Locked for this deadline" : "Recommendation"}</span>
        <strong className={plan.chip.recommended ? "tone-warn" : undefined}>{plan.chip.recommended ? `Play ${CHIP_LABEL[plan.chip.recommended]}` : "Hold your chips"}</strong>
        <p className="muted">{plan.chip.recommended ? `The ${CHIP_LABEL[plan.chip.recommended]} case cleared the engine's threshold (score ${fixed(plan.chip.score, 2)}). Check team news before committing.` : "No chip clears the evidence bar this week. Chips are worth most in doubles, blanks or a squad crisis, so FPL-AI defaults to holding."}</p>
      </div>
      <div className="chip-grid">
        {chips.map((chip) => (
          <span key={chip.chip} className={`chip-pill chip-${chip.status}`}>
            <b>{chip.label}</b>
            <small>{chip.status === "available" ? "Available" : chip.status === "used" ? "Used this half" : "Unknown"}</small>
          </span>
        ))}
      </div>
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
      <p className="card-note">Darker cells mean more expected points. Totals are minutes-adjusted. Bench players are dimmed.</p>
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

export function PlanWorkspace() {
  const { ready, dashboard, loading, error, refresh, state, squad, plan, marketLoading } = useCockpit();
  const snapshot = useMemo(
    () => (plan && state.actionsOpen && dashboard ? planSnapshot(plan, state.targetEvent, state.modelVersion, dashboard.meta.generated_at) : null),
    [plan, state.actionsOpen, state.targetEvent, state.modelVersion, dashboard],
  );
  const { history, change } = usePlanHistory(snapshot);

  if (!ready || (!dashboard && loading)) return <DataState title="Loading your plan" loading>Running the decision engine on your squad.</DataState>;
  if (!dashboard && error) return <DataState tone="error" title="Your plan could not be loaded" action={<button className="btn btn-sm btn-primary" onClick={() => void refresh()}>Try again</button>}>{error}</DataState>;
  if (!dashboard) return <DataState tone="empty" title="Connect a team to build a plan" action={<Link className="btn btn-sm btn-primary" href="/">Connect your team</Link>}>Plans use your squad, bank, free transfers and chip history.</DataState>;
  if (!plan) {
    return (
      <div>
        <header className="page-head"><div><span className="eyebrow">Plan & Transfers</span><h1>No plan available</h1></div></header>
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
          <p>{isTransfer ? "The engine found a move that clears its threshold after cost and uncertainty." : "No transfer clears the threshold. Rolling banks the transfer for next week's team news."}</p>
        </div>
        <div className="page-head-actions">
          {plan.confidence ? <span className={`pill ${plan.confidence.label === "HIGH" ? "pill-pos" : plan.confidence.label === "LOW" ? "pill-warn" : "pill-accent"}`}>{sentenceCase(plan.confidence.label)} confidence</span> : null}
          <span className="pill">{plan.freeTransfers == null ? "Free transfers unknown" : `${plan.freeTransfers} FT`}</span>
          <span className="pill">Bank {price(plan.bank)}</span>
        </div>
      </header>

      {locked ? <DataState tone="stale" compact title={state.liveActive ? "Gameweek in progress" : "Deadline passed"}>These recommendations target GW{state.targetEvent}, whose deadline has passed. They are shown for context and cannot be acted on.</DataState> : null}
      {marketLoading ? <p className="faint loading-note">Loading incoming-player projections…</p> : null}

      <div className="plan-grid">
        <Card id="transfers" title="Transfer decision" icon={<Repeat2 size={16} />} source="model" tone={isTransfer ? "accent" : undefined} className="plan-transfer">
          <div className="verdict verdict-inline">
            <strong className={`verdict-word verdict-${isTransfer ? "transfer" : "hold"}`}>{isTransfer ? "Transfer" : "Hold"}</strong>
            {isTransfer ? plan.recommended.moves.map((move) => <MoveRow key={`${move.outId}-${move.inId}`} move={move} />) : plan.bestRejected ? (
              <div className="rejected"><span className="eyebrow">Best move found, below threshold</span>{plan.bestRejected.moves.map((move) => <MoveRow key={`${move.outId}-${move.inId}`} move={move} compact />)}</div>
            ) : <p className="muted">No evaluated transfer improves the squad.</p>}
            {(isTransfer ? plan.recommended : plan.bestRejected) ? <ScenarioMetrics scenario={isTransfer ? plan.recommended : plan.bestRejected!} freeTransfers={plan.freeTransfers} /> : null}
          </div>
        </Card>

        <div className="stack">
          <CaptainCompare plan={plan} squad={squad} />
          <ChipCard plan={plan} locked={locked} />
        </div>
        <ScenarioCompare plan={plan} />
        <div className="plan-wide"><HorizonGrid squad={squad} /></div>
        <Card id="why" title="Why this plan" icon={<Lightbulb size={16} />} className="plan-why">
          <ExplainPlan plan={plan} modelVersion={state.modelVersion} />
        </Card>
        <div className="stack">
          <RiskCard squad={squad} />
          <Card title="Plan history" icon={<History size={16} />} source="derived">
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
        </div>
      </div>
    </div>
  );
}
