"use client";

import { CalendarClock } from "lucide-react";

import { Card } from "@/components/ui/primitives";
import type { TwoWeekMove, TwoWeekPlan, TwoWeekSequence } from "@/lib/contracts";
import { fixed, signed } from "@/lib/format";

const moveText = (moves: TwoWeekMove[]) => moves.map((move) => `${move.player_out} → ${move.player_in}`).join(", ");

function nowLabel(sequence: TwoWeekSequence): string {
  if (!sequence.transfers_now) return "Hold now";
  return `${sequence.transfers_now} now${sequence.hits_now ? ` (−${sequence.hits_now * 4})` : ""}`;
}

function nextLabel(sequence: TwoWeekSequence): string {
  if (!sequence.moves_next.length) return `Next week, if current info holds: no transfer (${sequence.free_transfers_next} free transfer${sequence.free_transfers_next === 1 ? "" : "s"} banked)`;
  const free = Math.min(sequence.moves_next.length, sequence.free_transfers_next);
  return `Next week, if current info holds: ${moveText(sequence.moves_next)} · ${free} free${sequence.hits_next ? `, −${sequence.hits_next * 4}` : ""}`;
}

/** One line for the transfer card: what the chosen plan does next week. */
export function NextWeekLine({ plan, transfersNow }: { plan: TwoWeekPlan | null; transfersNow: number }) {
  const sequence = plan?.sequences.find((item) => item.transfers_now === transfersNow);
  if (!sequence || !sequence.moves_next.length) return null;
  return (
    <p className="two-week-line">
      <CalendarClock size={15} aria-hidden="true" />
      <span><b>{transfersNow ? "Then next week" : "Next week instead"}, if current info holds:</b> {moveText(sequence.moves_next)}{sequence.hits_next ? ` (−${sequence.hits_next * 4})` : " with your free transfer" + (sequence.moves_next.length > 1 ? "s" : "")}.</span>
    </p>
  );
}

/** Every number of transfers now, each with its best follow-up next week. */
export function TwoWeekCard({ plan, transfersNow }: { plan: TwoWeekPlan; transfersNow: number }) {
  const best = Math.max(...plan.sequences.map((item) => item.score_vs_hold));
  return (
    <Card id="two-week" title="Now and next-week plan" eyebrow={`${plan.horizon ?? "Multi"}-Gameweek scoring horizon`} icon={<CalendarClock size={16} />} source={["model", "derived"]}>
      {!plan.sequences.length ? <p className="muted">No follow-up sequence was returned.</p> : null}
      <ul className="two-week-list">
        {plan.sequences.map((sequence) => {
          const chosen = sequence.transfers_now === transfersNow;
          return (
            <li key={sequence.transfers_now} className={`two-week-row${chosen ? " is-recommended" : ""}`}>
              <div className="two-week-head">
                {chosen ? <span className="pill pill-accent">Recommended</span> : null}
                <b>{nowLabel(sequence)}</b>
                <span className={`two-week-score num ${sequence.score_vs_hold >= best - 1e-6 && sequence.score_vs_hold > 0 ? "tone-pos" : ""}`}>Decision score: {signed(sequence.score_vs_hold)}</span>
              </div>
              {sequence.moves_now.length ? <p>Now: {moveText(sequence.moves_now)}</p> : null}
              <p>Projected net gain: {sequence.projected_net_gain == null ? "Unavailable" : `${signed(sequence.projected_net_gain)} xP`}</p>
              <p className="muted">Projected gain before hits: {sequence.projected_gain == null ? "Unavailable" : `${signed(sequence.projected_gain)} xP`} · Weighted gain: {signed(sequence.weighted_gain_vs_hold)}</p>
              <p className="muted">Hit cost: {sequence.hit_cost == null ? "Unavailable" : sequence.hit_cost ? `−${sequence.hit_cost}` : "0"} · Safety margin: {sequence.risk_margin == null ? "Unavailable" : fixed(sequence.risk_margin)} · Terminal roll value: {sequence.roll_value == null ? "Unavailable" : fixed(sequence.roll_value)}</p>
              <p className="muted">{nextLabel(sequence)}</p>
            </li>
          );
        })}
      </ul>
      <details className="card-more">
        <summary>How is this worked out?</summary>
        <p className="card-note">
        Each row evaluates transfers now with a follow-up next week using today&apos;s projections. Next-week moves apply only if current info holds.
        Unused free transfers carry over (up to five); extra moves cost −4.
        The baseline is hold now, then optimize next week with the allowed moves, rather than keeping the squad unchanged throughout.
        Projected gains are unweighted FPL points relative to that baseline; net gain subtracts the difference in actual hit costs.
        Decision score compares weighted gains after differences in hits and policy safety margins, plus terminal roll value; the displayed costs and roll value are absolute for each row.
        {plan.weights?.length ? ` Horizon weights: ${plan.weights.join(", ")}.` : " Horizon weights unavailable."}
        The conservative policy can favor fewer moves now, even when another row scores higher.
        {plan.optimality_known === true ? " Follow-ups were solved within the evaluated candidate pool and current squads." : " Search optimality is unconfirmed; evaluated sequences may be incomplete."}
        </p>
      </details>
    </Card>
  );
}
