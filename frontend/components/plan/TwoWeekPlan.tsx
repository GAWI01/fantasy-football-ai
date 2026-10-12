"use client";

import { CalendarClock } from "lucide-react";

import { Card } from "@/components/ui/primitives";
import type { TwoWeekMove, TwoWeekPlan, TwoWeekSequence } from "@/lib/contracts";
import { signed } from "@/lib/format";

const moveText = (moves: TwoWeekMove[]) => moves.map((move) => `${move.player_out} → ${move.player_in}`).join(", ");

function nowLabel(sequence: TwoWeekSequence): string {
  if (!sequence.transfers_now) return "Hold now";
  return `${sequence.transfers_now} now${sequence.hits_now ? ` (−${sequence.hits_now * 4})` : ""}`;
}

function nextLabel(sequence: TwoWeekSequence): string {
  if (!sequence.moves_next.length) return `Next week: nothing (${sequence.free_transfers_next} free transfer${sequence.free_transfers_next === 1 ? "" : "s"} banked)`;
  const free = Math.min(sequence.moves_next.length, sequence.free_transfers_next);
  return `Next week: ${moveText(sequence.moves_next)} · ${free} free${sequence.hits_next ? `, −${sequence.hits_next * 4}` : ""}`;
}

/** One line for the transfer card: what the chosen plan does next week. */
export function NextWeekLine({ plan, transfersNow }: { plan: TwoWeekPlan | null; transfersNow: number }) {
  const sequence = plan?.sequences.find((item) => item.transfers_now === transfersNow);
  if (!sequence || !sequence.moves_next.length) return null;
  return (
    <p className="two-week-line">
      <CalendarClock size={15} aria-hidden="true" />
      <span><b>{transfersNow ? "Then next week" : "Next week instead"}:</b> {moveText(sequence.moves_next)}{sequence.hits_next ? ` (−${sequence.hits_next * 4})` : " with your free transfer" + (sequence.moves_next.length > 1 ? "s" : "")}.</span>
    </p>
  );
}

/** Every number of transfers now, each with its best follow-up next week. */
export function TwoWeekCard({ plan, transfersNow }: { plan: TwoWeekPlan; transfersNow: number }) {
  const best = Math.max(...plan.sequences.map((item) => item.score_vs_hold));
  return (
    <Card id="two-week" title="Two-week plan" eyebrow="Now and next week" icon={<CalendarClock size={16} />} source={["model", "derived"]}>
      <ul className="two-week-list">
        {plan.sequences.map((sequence) => {
          const chosen = sequence.transfers_now === transfersNow;
          return (
            <li key={sequence.transfers_now} className={`two-week-row${chosen ? " is-recommended" : ""}`}>
              <div className="two-week-head">
                {chosen ? <span className="pill pill-accent">Recommended</span> : null}
                <b>{nowLabel(sequence)}</b>
                <span className={`two-week-score num ${sequence.score_vs_hold >= best - 1e-6 && sequence.score_vs_hold > 0 ? "tone-pos" : ""}`}>{signed(sequence.score_vs_hold)}</span>
              </div>
              {sequence.moves_now.length ? <p>Now: {moveText(sequence.moves_now)}</p> : null}
              <p className="muted">{nextLabel(sequence)}</p>
            </li>
          );
        })}
      </ul>
      <p className="card-note">
        Each row is the best plan over this Gameweek and the next for that many transfers now, with FPL&apos;s rules between them: unused free transfers carry over (up to five) and extra moves cost −4.
        The score is weighted five-Gameweek points against holding, after hits, safety margins and the value of transfers still banked.
        The engine uses this to make fewer moves now when waiting a week is as good or better (for example a free move next week instead of a hit now), never to make more:
        team news arrives in between, and both weeks are planned on today&apos;s projections.
      </p>
    </Card>
  );
}
