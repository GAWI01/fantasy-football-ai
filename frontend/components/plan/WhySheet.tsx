"use client";

import { Sheet } from "@/components/ui/Sheet";
import { Meter, SourceBadge } from "@/components/ui/primitives";
import { sentenceCase } from "@/lib/format";
import type { GameweekPlan } from "@/lib/model/plan";

const COMPONENT_COPY: Record<string, { label: string; hint: string }> = {
  decision_margin: { label: "Decision margin", hint: "How clearly the chosen action beats the next best one." },
  minutes_certainty: { label: "Minutes certainty", hint: "How settled your squad's expected minutes are." },
  fixture_certainty: { label: "Fixture coverage", hint: "How much of the five-GW horizon has fixture data." },
  signal_agreement: { label: "Signal agreement", hint: "Whether next-GW and multi-GW signals point the same way." },
};

function signalStrength(value: number): string {
  return value >= 0.75 ? "Strong" : value >= 0.5 ? "Moderate" : "Weak";
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
          <p className="faint">A rule-based summary of the four signals below, not a probability that the move pays off.</p>
          <div className="why-meters">
            {Object.entries(confidence.components).map(([key, value]) => (
              <div key={key} className="why-meter">
                <div className="row"><strong>{COMPONENT_COPY[key]?.label ?? sentenceCase(key)}</strong><span className="spacer" /><span>{signalStrength(value)}</span></div>
                <Meter value={value} label={COMPONENT_COPY[key]?.label ?? key} tone={value >= 0.75 ? "pos" : value >= 0.5 ? "accent" : "warn"} />
                <small className="faint">{COMPONENT_COPY[key]?.hint}</small>
              </div>
            ))}
          </div>
        </section>
      ) : null}
      <section className="why-method">
        <h3 className="why-title">How to read the numbers</h3>
        <ul>
          <li><b>Next GW</b> is the native model projection for the coming Gameweek. Projections are forecasts, never results.</li>
          <li><b>5-GW gain</b> adds four further Gameweeks by scaling next GW&rsquo;s forecast to each later fixture&rsquo;s official difficulty and home/away. It is a planning guide, not four separate model forecasts.</li>
          <li><b>Hits</b> cost 4 points per transfer beyond your free transfers. The engine only proposes a hit when the multi-GW edge clearly exceeds it.</li>
          <li>Captain and vice-captain are always chosen from players you own.</li>
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
