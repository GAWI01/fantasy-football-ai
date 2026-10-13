"use client";

import { CalendarRange } from "lucide-react";

import { DataState } from "@/components/states/DataState";
import { Card, Skeleton } from "@/components/ui/primitives";
import type { ChipPlanEntry } from "@/lib/contracts";
import { useChipPlan } from "@/lib/hooks/data";

function PlanRow({ entry }: { entry: ChipPlanEntry }) {
  return (
    <li className={`season-chip${entry.gameweek ? " is-set" : ""}`}>
      <span className="season-chip-week">{entry.gameweek ? `GW${entry.gameweek}` : "Wait"}</span>
      <span className="season-chip-text">
        <b>{entry.label}</b>
        <small>{entry.reason}</small>
      </span>
    </li>
  );
}

/** The rest of the season's chips, planned around blank and double Gameweeks in the fixture list. */
export function ChipSeasonPlan({ teamId, freeTransfers }: { teamId: string | null; freeTransfers?: number | null }) {
  const plan = useChipPlan(teamId, freeTransfers);
  const data = plan.data?.data;
  return (
    <Card id="chip-season" title="Season chip plan" eyebrow="Blank and double Gameweeks" icon={<CalendarRange size={16} />} source={["official", "model"]}>
      {plan.loading && !data ? <Skeleton lines={4} /> : null}
      {plan.error && !data ? <DataState compact tone="error" title="The season plan is unavailable" action={<button className="btn btn-sm" onClick={plan.reload}>Try again</button>}>{plan.error}</DataState> : null}
      {data ? (
        <>
          <span className="eyebrow">Your chips for GW{data.period.first}–{data.period.last}</span>
          {data.plans.length ? <ul className="season-chips">{data.plans.map((entry) => <PlanRow key={entry.chip} entry={entry} />)}</ul> : <p className="muted">You have no chips left in this period.</p>}
          {data.next_period ? (
            <>
              <span className="eyebrow season-next">From GW{data.next_period.first}: all four chips again</span>
              {data.next_period.plans.some((entry) => entry.gameweek) ? (
                <ul className="season-chips">{data.next_period.plans.map((entry) => <PlanRow key={`next-${entry.chip}`} entry={entry} />)}</ul>
              ) : (
                <p className="muted season-wait">No blank or double Gameweek is scheduled after GW{data.next_period.first - 1} yet, so there is nothing to plan around. Keep all four until FPL schedules them.</p>
              )}
            </>
          ) : null}
          {data.timeline.length ? (
            <div className="season-timeline" aria-label="Blank and double Gameweeks">
              {data.timeline.map((week) => (
                <span key={week.gameweek} className="season-week">
                  <b>GW{week.gameweek}</b>
                  {week.double_clubs ? <small className="tone-pos">{week.double_clubs} clubs play twice</small> : null}
                  {week.blank_clubs ? <small className="tone-neg">{week.blank_clubs} clubs blank</small> : null}
                </span>
              ))}
            </div>
          ) : <p className="card-note">FPL has not scheduled any blank or double Gameweeks yet. This plan updates by itself when it does.</p>}
          {data.unscheduled.length ? (
            <p className="card-note"><b>Matches without a date:</b> {data.unscheduled.map((match) => `${match.home} v ${match.away}`).join(", ")}. These usually become double Gameweeks later.</p>
          ) : null}
        </>
      ) : null}
    </Card>
  );
}
