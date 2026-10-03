"use client";

import { AlertTriangle, ArrowRight, CircleCheck, Crown, Info, Layers, Shield, ShieldAlert, Sparkles, Zap } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PlayerCard } from "@/components/player/PlayerCard";
import { PlayerChip } from "@/components/player/PlayerChip";
import { WhySheet } from "@/components/plan/WhySheet";
import { Delta, SourceBadge } from "@/components/ui/primitives";
import { fixed, price, sentenceCase } from "@/lib/format";
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

export function ScenarioMetrics({ scenario, freeTransfers }: { scenario: ScenarioView; freeTransfers: number | null }) {
  return (
    <dl className="metrics">
      <div>
        <dt>Next GW <SourceBadge kind="derived" /></dt>
        <dd><Delta value={scenario.nextGwGain} unit=" xP" /></dd>
      </div>
      <div>
        <dt>5-GW gain <SourceBadge kind="model" /></dt>
        <dd><Delta value={scenario.horizonGain} unit=" xP" /></dd>
      </div>
      <div>
        <dt>Hit cost</dt>
        <dd className={scenario.hit ? "tone-neg" : undefined}>{scenario.hit == null ? "Unknown" : scenario.hit ? `−${scenario.hit}` : "Free"}</dd>
      </div>
      <div>
        <dt>5-GW net <SourceBadge kind="derived" /></dt>
        <dd><Delta value={scenario.horizonNet} unit=" xP" /></dd>
      </div>
      <div className="metrics-note">
        <dt className="sr-only">Free transfers</dt>
        <dd>{freeTransfers == null ? "Free transfers unknown" : `${freeTransfers} free transfer${freeTransfers === 1 ? "" : "s"} available`}</dd>
      </div>
    </dl>
  );
}

function holdCopy(plan: GameweekPlan): string {
  if (plan.bestRejected) {
    return "The best move found does not clear the decision threshold after cost and uncertainty. Bank the transfer and keep flexibility.";
  }
  return "No evaluated transfer improves the squad enough. Bank the transfer and keep flexibility.";
}

export function GameweekPlanCard({
  plan,
  event,
  modelVersion,
  locked = false,
}: {
  plan: GameweekPlan;
  event: number | null;
  modelVersion: string | null;
  locked?: boolean;
}) {
  const [whyOpen, setWhyOpen] = useState(false);
  const isTransfer = plan.verdict === "TRANSFER";
  const scenario = isTransfer ? plan.recommended : plan.bestRejected;
  const confidence = plan.confidence;
  const benchOutfield = plan.bench.filter((player) => player.position !== "GKP");
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
          {confidence ? <span className={`pill ${confidence.label === "HIGH" ? "pill-pos" : confidence.label === "LOW" ? "pill-warn" : "pill-accent"}`}>{sentenceCase(confidence.label)} confidence · {Math.round(confidence.score * 100)}%</span> : null}
          <SourceBadge kind="model" />
        </div>
      </header>

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
          {scenario ? <ScenarioMetrics scenario={scenario} freeTransfers={plan.freeTransfers} /> : null}
          {isTransfer && (plan.recommended.hit ?? 0) > 0 ? (
            <p className="hit-note"><Info size={14} aria-hidden="true" />This plan takes a −{plan.recommended.hit} hit. The engine only accepts hits when the multi-GW edge clearly exceeds the cost.</p>
          ) : null}
        </div>

        <div className="hero-side">
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
          <div className="decision-tiles">
            <div className="tile">
              <span className="tile-label"><Zap size={14} aria-hidden="true" />Chip</span>
              <strong className={`tile-word${plan.chip.recommended ? " tone-warn" : ""}`}>{plan.chip.recommended ? CHIP_LABEL[plan.chip.recommended] : "Hold chips"}</strong>
              <small className="faint">{plan.chip.recommended ? "Opportunity cleared the threshold" : "No chip clears the evidence bar"}</small>
            </div>
            <div className="tile">
              <span className="tile-label"><Layers size={14} aria-hidden="true" />Bench order</span>
              <ol className="bench-mini">
                {benchOutfield.map((player) => <li key={player.id}>{player.name}<small> {fixed(player.xp)}</small></li>)}
                {!benchOutfield.length ? <li className="faint">Unavailable</li> : null}
              </ol>
            </div>
            <div className={`tile tile-risk tile-risk-${plan.mainRisk.tone}`}>
              <span className="tile-label">{riskIcon}Main risk</span>
              <strong className="tile-risk-title">{plan.mainRisk.title}</strong>
              <small>{plan.mainRisk.detail}</small>
            </div>
          </div>
        </div>
      </div>

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
