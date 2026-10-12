"use client";

import { Sheet } from "@/components/ui/Sheet";
import { SourceBadge } from "@/components/ui/primitives";
import { sentenceCase } from "@/lib/format";
import type { GameweekPlan } from "@/lib/model/plan";

function points(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";
}

export function ExplainPlan({ plan, modelVersion }: { plan: GameweekPlan; modelVersion: string | null }) {
  const confidence = plan.confidence;
  return (
    <div className="why">
      <section>
        <h3 className="why-title">Reasons <SourceBadge kind="model" /></h3>
        {plan.insights.length ? (
          <ul className="why-list">
            {plan.insights.map((insight) => (
              <li key={`${insight.type}-${insight.reason}`} className={`why-item why-${insight.severity.toLowerCase()}`}>
                <span className="eyebrow">{sentenceCase(insight.type)}</span>
                <p>{insight.reason}</p>
              </li>
            ))}
          </ul>
        ) : <p className="faint">The model did not return written reasons for this plan.</p>}
      </section>
      {confidence ? (
        <section>
          <h3 className="why-title">Confidence: {sentenceCase(confidence.label)}</h3>
          <p className="faint">
            {confidence.label === "UNKNOWN"
              ? confidence.basis ?? "There was no alternative action to compare against."
              : "How clearly this action beats the next-best one, measured against the projection uncertainty of the players involved. A heuristic, not a probability that the move pays off."}
          </p>
          {confidence.label !== "UNKNOWN" ? (
            <dl className="metrics">
              <div><dt>Margin over next best</dt><dd>{points(confidence.components.decision_margin)} decision score</dd></div>
              <div><dt>Projection uncertainty</dt><dd>±{points(confidence.components.uncertainty)} xP</dd></div>
            </dl>
          ) : null}
          {confidence.minutes_doubts?.length ? <p className="card-note">Minutes doubt: {confidence.minutes_doubts.join("; ")}.</p> : null}
        </section>
      ) : null}
      <section className="why-method">
        <h3 className="why-title">How to read the numbers</h3>
        <ul>
          <li><b>Next GW</b> is the change in the projected points of your best starting XI and captain for the coming Gameweek. Bench players count only as cover for absences. Projections are forecasts, never results.</li>
          <li><b>Projected gain</b> sums unweighted forecast points over the available {plan.horizon ?? "multi"}-Gameweek horizon. Net after hits subtracts actual hit costs. Decision score separately weights later Gameweeks less and includes safety margins and the policy value of banked transfers. Later Gameweeks scale the model&rsquo;s forecast to each fixture&rsquo;s official difficulty and home/away, with each Gameweek&rsquo;s own availability (a one-match ban only costs one Gameweek). It is a planning guide, not five separate model forecasts.</li>
          <li><b>Holding is always an option.</b> The planner assigns a policy value to banked transfers and considers next-week follow-ups. Its conservative policy can recommend fewer moves now even if another option has a higher single-stage decision score.</li>
          <li><b>Hits</b> cost 4 points per transfer beyond your free transfers. The engine takes a hit only when the weighted horizon gain beats the hit plus a safety margin.</li>
          <li><b>Captain and lineup</b> are picked from your squad after the recommended transfers, so a player you buy can start or wear the armband. If you hold, they come from the players you own now.</li>
        </ul>
        {modelVersion ? <p className="faint">Model artifact: <span className="mono">{modelVersion}</span></p> : null}
      </section>
    </div>
  );
}

export function WhySheet({ open, onClose, plan, modelVersion }: { open: boolean; onClose: () => void; plan: GameweekPlan; modelVersion: string | null }) {
  return (
    <Sheet open={open} onClose={onClose} title="Why this plan" subtitle="The evidence behind the recommendation">
      <ExplainPlan plan={plan} modelVersion={modelVersion} />
    </Sheet>
  );
}
