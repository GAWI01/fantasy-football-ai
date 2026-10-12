"use client";

import { AlertTriangle, ArrowRight, CircleCheck, Crown, Info, Shield, ShieldAlert, Sparkles, Zap } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PlayerCard } from "@/components/player/PlayerCard";
import { PlayerChip } from "@/components/player/PlayerChip";
import { FreeTransfersControl } from "@/components/plan/FreeTransfersControl";
import { WhySheet } from "@/components/plan/WhySheet";
import { Delta, SourceBadge, SourceScope } from "@/components/ui/primitives";
import { fixed, price, sentenceCase, signed } from "@/lib/format";
import { CHIP_LABEL, type GameweekPlan, type ScenarioView, type TransferMove } from "@/lib/model/plan";

export function MoveRow({ move, compact = false }: { move: TransferMove; compact?: boolean }) {
  if (!compact) {
    const gain = move.inXp != null && move.outXp != null ? move.inXp - move.outXp : null;
    return (
      <div className="move move-cards">
        <PlayerCard
          tone="out"
          tag="Out"
          name={move.outName}
          team={move.out?.team}
          teamShort={move.out?.teamShort}
          position={move.out?.position ?? move.position}
          value={fixed(move.outXp)}
          meta={`Sells ${price(move.out?.sellingPrice ?? move.out?.price)}`}
        />
        <span className="move-swap">
          <ArrowRight size={22} role="img" aria-label="replaced by" />
          {gain != null ? <span className="move-gain"><Delta value={gain} /><small>next GW</small></span> : null}
        </span>
        <PlayerCard
          tone="in"
          tag="In"
          name={move.inName}
          team={move.inTeam}
          teamShort={move.inTeamShort}
          position={move.position}
          value={fixed(move.inXp)}
          meta={`Costs ${price(move.inPrice)}`}
        />
      </div>
    );
  }
  return (
    <div className="move move-compact">
      <div className="move-side move-out">
        <span className="move-tag">Out</span>
        <PlayerChip
          name={move.outName}
          team={move.out?.team}
          teamShort={move.out?.teamShort}
          position={move.out?.position ?? move.position}
          meta={<>{price(move.out?.sellingPrice ?? move.out?.price)} · <span className="tone-accent">{fixed(move.outXp)} xP</span></>}
          size={30}
        />
      </div>
      <ArrowRight className="move-arrow" size={18} aria-label="replaced by" />
      <div className="move-side move-in">
        <span className="move-tag">In</span>
        <PlayerChip
          name={move.inName}
          team={move.inTeam}
          teamShort={move.inTeamShort}
          position={move.position}
          meta={<>{price(move.inPrice)} · <span className="tone-accent">{fixed(move.inXp)} xP</span></>}
          size={30}
        />
      </div>
    </div>
  );
}

export function ScenarioMetrics({ scenario, plan }: { scenario: ScenarioView; plan: GameweekPlan }) {
  return (
    <dl className="metrics">
      <div>
        <dt>Next GW <SourceBadge kind="derived" /></dt>
        <dd><Delta value={scenario.nextGwGain} unit=" xP" animate /></dd>
      </div>
      <div>
        <dt>5-GW gain <SourceBadge kind="derived" /></dt>
        <dd><Delta value={scenario.horizonGain} unit=" xP" animate /></dd>
      </div>
      <div>
        <dt>Hit cost</dt>
        <dd className={scenario.hit ? "tone-neg" : undefined}>{scenario.hit == null ? "Unknown" : scenario.hit ? `−${scenario.hit}` : "Free"}</dd>
      </div>
      <div>
        <dt>5-GW net <SourceBadge kind="derived" /></dt>
        <dd><Delta value={scenario.horizonNet} unit=" xP" animate /></dd>
      </div>
      <div className="metrics-note">
        <dt className="sr-only">Free transfers</dt>
        <dd><FreeTransfersControl count={plan.freeTransfers} source={plan.freeTransfersSource} /></dd>
      </div>
      {plan.budgetIsEstimate && scenario.moves.length > 0 ? <div className="metrics-note"><dt className="sr-only">Affordability</dt><dd>Affordability is estimated from market prices. Check your actual selling prices in FPL before making the move.</dd></div> : null}
    </dl>
  );
}

function holdCopy(plan: GameweekPlan): string {
  const best = plan.bestRejected;
  if (best) {
    const roll = best.rollValue ? ` A rolled free transfer is worth about ${fixed(best.rollValue)} xP next week.` : "";
    return `The best move found adds ${signed(best.horizonGain)} xP over five Gameweeks${best.hit ? ` after a −${best.hit} hit` : ""}, which does not beat keeping the transfer.${roll}`;
  }
  return "No legal move improves your projected lineup. Bank the transfer and keep flexibility.";
}

export function ProvisionalPill({ cutoff, event }: { cutoff: number; event: number | null }) {
  const live = event != null ? event - 1 : null;
  return (
    <span className="pill pill-accent" title={`GW${live ?? "—"} is still being played. This forecast uses results up to GW${cutoff} and updates once GW${live ?? "—"} is final.`}>
      Provisional forecast
    </span>
  );
}

/** When holding: which chips you still have and the week that suits each. */
export function chipHint(plan: GameweekPlan): string | null {
  const available = plan.chip.outlook.filter((item) => item.available);
  if (!plan.chip.outlook.length) return null;
  if (!available.length) return "No chips left this half";
  return available.map((item) => `${item.label}: ${item.best_window ? `best GW${item.best_window.gameweek}` : "no clear week yet"}`).join(" · ");
}

export function GameweekPlanCard({
  plan,
  event,
  modelVersion,
  locked = false,
  provisionalCutoff = null,
}: {
  plan: GameweekPlan;
  event: number | null;
  modelVersion: string | null;
  locked?: boolean;
  /** Set while the previous Gameweek is still played: the forecast uses results up to this Gameweek. */
  provisionalCutoff?: number | null;
}) {
  const [whyOpen, setWhyOpen] = useState(false);
  const isTransfer = plan.verdict === "TRANSFER";
  const scenario = isTransfer ? plan.recommended : plan.bestRejected;
  const confidence = plan.confidence;
  const riskIcon = plan.mainRisk.tone === "calm" ? <CircleCheck size={16} aria-hidden="true" /> : plan.mainRisk.tone === "risk" ? <ShieldAlert size={16} aria-hidden="true" /> : <AlertTriangle size={16} aria-hidden="true" />;

  return (
    <section className={`plan-hero plan-hero-${isTransfer ? "transfer" : "hold"}`} aria-labelledby="gw-plan-title">
      <header className="hero-band">
        <span className="hero-gw" aria-hidden="true">GW{event ?? "—"}</span>
        <div className="hero-title">
          <span className="eyebrow">Gameweek {event ?? "—"} plan · {isTransfer ? "Transfer" : "No transfer"}</span>
          <h2 id="gw-plan-title" className="sr-only">Gameweek {event ?? ""} plan</h2>
          <strong className={`verdict-word verdict-${isTransfer ? "transfer" : "hold"}`}>
            {isTransfer ? (plan.recommended.moves.length > 1 ? `${plan.recommended.moves.length} transfers` : "Make the move") : "Hold"}
          </strong>
        </div>
        <div className="hero-meta">
          {locked ? <span className="pill pill-warn">Read-only · deadline passed</span> : null}
          {provisionalCutoff != null ? <ProvisionalPill cutoff={provisionalCutoff} event={event} /> : null}
          {confidence ? <span className={`pill ${confidence.label === "HIGH" ? "pill-pos" : confidence.label === "LOW" ? "pill-warn" : "pill-accent"}`}>{sentenceCase(confidence.label)} confidence</span> : null}
          <SourceBadge kind="model" pinned />
          {scenario ? <SourceBadge kind="derived" pinned /> : null}
        </div>
      </header>

      <SourceScope kinds={scenario ? ["model", "derived"] : ["model"]}>
      <div className="plan-hero-grid">
        <div className="verdict">
          {isTransfer ? (
            <div className="move-list">{plan.recommended.moves.map((move) => <MoveRow key={`${move.outId}-${move.inId}`} move={move} />)}</div>
          ) : (
            <p className="verdict-copy">{holdCopy(plan)}</p>
          )}
          {!isTransfer && plan.bestRejected ? (
            <div className="rejected">
              <span className="eyebrow">Best move found, not recommended</span>
              {plan.bestRejected.moves.map((move) => <MoveRow key={`${move.outId}-${move.inId}`} move={move} compact />)}
            </div>
          ) : null}
          {scenario ? <ScenarioMetrics scenario={scenario} plan={plan} /> : null}
          {isTransfer && (plan.recommended.hit ?? 0) > 0 ? (
            <p className="hit-note"><Info size={14} aria-hidden="true" />This plan takes a −{plan.recommended.hit} hit. The engine only accepts hits when the multi-GW edge clearly exceeds the cost.</p>
          ) : null}
        </div>

        <ul className="hero-lines">
          <li className="hero-line">
            <Crown size={16} aria-hidden="true" className="tone-accent" />
            <span>
              <span className="hero-line-label">Captain</span>
              {plan.captain ? (
                <>
                  <b>{plan.captain.name}</b> <span className="tone-accent num">{fixed(plan.captain.xp)} xP</span>
                  {plan.captain.opponent ? <span className="faint"> · {plan.captain.opponent}{plan.captain.home == null ? "" : plan.captain.home ? " (H)" : " (A)"}</span> : null}
                  {plan.vice ? <span className="faint"> · Vice </span> : null}{plan.vice ? <b>{plan.vice.name}</b> : null}
                </>
              ) : <span className="faint">Unavailable</span>}
            </span>
          </li>
          <li className={`hero-line hero-line-risk tone-line-${plan.mainRisk.tone}`}>
            {riskIcon}
            <span>
              <span className="hero-line-label">Main risk</span>
              <b className="tile-risk-title">{plan.mainRisk.title}</b>
              <small>{plan.mainRisk.detail}</small>
            </span>
          </li>
          <li className={`hero-line${plan.chip.recommended ? " hero-line-chip" : ""}`}>
            <Zap size={16} aria-hidden="true" className={plan.chip.recommended ? "tone-warn" : undefined} />
            <span>
              <span className="hero-line-label">Chip</span>
              <b className={plan.chip.recommended ? "tone-warn" : undefined}>{plan.chip.recommended ? `Play ${CHIP_LABEL[plan.chip.recommended]}` : "Hold chips"}</b>
              {plan.chip.recommended && plan.chip.reason ? <small>{plan.chip.reason}</small> : null}
            </span>
          </li>
        </ul>
      </div>
      </SourceScope>

      <footer className="plan-hero-foot">
        <button type="button" className="btn btn-sm" onClick={() => setWhyOpen(true)}><Info size={14} aria-hidden="true" />Why this plan</button>
        <Link className="btn btn-sm" href="/plan#compare">Compare options</Link>
        <Link className="btn btn-sm btn-ghost" href="/team">Set lineup<ArrowRight size={14} aria-hidden="true" /></Link>
        <span className="plan-hero-disclaimer">Recommendation only. Make changes in the official FPL app.</span>
      </footer>
      <WhySheet open={whyOpen} onClose={() => setWhyOpen(false)} plan={plan} modelVersion={modelVersion} />
    </section>
  );
}


/** Captain, vice and the projected score, for the Lineup & captain section. */
export function PlanLineupDetails({ plan }: { plan: GameweekPlan }) {
  return (
    <div className="armband">
      {plan.captain ? (
        <PlayerCard
          tone="captain"
          tag={<><Crown size={12} aria-hidden="true" />Captain</>}
          badge="C"
          name={plan.captain.name}
          team={plan.captain.team}
          teamShort={plan.captain.teamShort}
          position={plan.captain.position}
          value={fixed(plan.captain.xp)}
          meta={plan.captain.opponent ? `${plan.captain.opponent}${plan.captain.home == null ? "" : plan.captain.home ? " (H)" : " (A)"}` : "Fixture —"}
        />
      ) : <div className="tile"><span className="tile-label"><Crown size={14} aria-hidden="true" />Captain</span><span className="faint">Unavailable</span></div>}
      <div className="armband-side">
        <div className="tile tile-score">
          <span className="tile-label"><Sparkles size={14} aria-hidden="true" />Projected score</span>
          <strong className="tile-number">{fixed(plan.projectedScore)}<small> xP</small></strong>
          <small className="faint">Best XI + captain{plan.formation ? ` · ${plan.formation}` : ""}</small>
        </div>
        <div className="tile">
          <span className="tile-label"><Shield size={14} aria-hidden="true" />Vice-captain</span>
          {plan.vice ? (
            <PlayerChip name={plan.vice.name} team={plan.vice.team} teamShort={plan.vice.teamShort} position={plan.vice.position} badge="V" meta={<span className="tone-accent">{fixed(plan.vice.xp)} xP</span>} size={32} />
          ) : <span className="faint">Unavailable</span>}
        </div>
      </div>
    </div>
  );
}

/** The chip call and the best week for each chip you still have. */
export function PlanChipDetails({ plan }: { plan: GameweekPlan }) {
  const hint = chipHint(plan);
  return (
    <div className="chip-details">
      <strong className={`tile-word${plan.chip.recommended ? " tone-warn" : ""}`}>{plan.chip.recommended ? `Play ${CHIP_LABEL[plan.chip.recommended]}` : "Hold chips"}</strong>
      <p className="muted">{plan.chip.recommended ? plan.chip.reason ?? "The chip case beats its evidence bar." : plan.chip.reason ?? "No chip clears the evidence bar this week."}</p>
      {hint ? <p className="faint">{hint}</p> : null}
      {plan.chipBudgetIsEstimate ? <p className="faint">Squad affordability estimated from market prices.</p> : null}
    </div>
  );
}

/** One line for a closed Chip section. */
export function chipSummary(plan: GameweekPlan): string {
  if (plan.chip.recommended) return `Play ${CHIP_LABEL[plan.chip.recommended]} this week`;
  const next = plan.chip.outlook.filter((item) => item.available && item.best_window).sort((left, right) => (left.best_window?.gameweek ?? 99) - (right.best_window?.gameweek ?? 99))[0];
  return next?.best_window ? `Hold chips · ${next.label} best in GW${next.best_window.gameweek}` : "Hold chips";
}
