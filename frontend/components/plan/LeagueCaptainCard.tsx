"use client";

import { Trophy } from "lucide-react";
import { useMemo, useState } from "react";

import { DataState } from "@/components/states/DataState";
import { Card, Skeleton } from "@/components/ui/primitives";
import { Term } from "@/components/ui/Term";
import type { LeagueCaptainCandidate } from "@/lib/contracts";
import { fixed, signed } from "@/lib/format";
import { useLeagueCaptain, useLeagues } from "@/lib/hooks/data";

const KIND: Record<LeagueCaptainCandidate["kind"], { label: string; tone: string }> = {
  safe: { label: "Safe", tone: "pill-pos" },
  differential: { label: "Differential", tone: "pill-warn" },
  split: { label: "Split", tone: "" },
};

function share(candidate: LeagueCaptainCandidate, rivals: number): string {
  const count = Math.round(candidate.rival_captain_share * rivals);
  if (!rivals) return "No rival squads to compare";
  if (!count) return "No rival captained him";
  return `${count} of ${rivals} rivals captained him`;
}

/**
 * The captain choice against one mini-league. A captain is worth the same on
 * average whoever else owns him; what the league changes is the risk, so the
 * card names the safe pick, the differential and the one your position calls for.
 */
export function LeagueCaptainCard({ teamId, freeTransfers }: { teamId: string | null; freeTransfers?: number | null }) {
  const leagues = useLeagues(teamId);
  // Leagues small enough for every rival squad to be read; the smallest first.
  const options = useMemo(() => (leagues.data?.data.leagues ?? [])
    .filter((league) => (league.managers ?? 1e9) <= 50)
    .sort((left, right) => (left.managers ?? 1e9) - (right.managers ?? 1e9)), [leagues.data]);
  const [chosen, setChosen] = useState<number | null>(null);
  const leagueId = chosen ?? options[0]?.league_id ?? null;
  const captain = useLeagueCaptain(leagueId, teamId, freeTransfers);
  const data = captain.data?.data;
  const pick = data?.pick;

  // No small league to compare against (or the list failed): the captain list above stands alone.
  if ((leagues.data && !options.length) || (leagues.error && !leagues.data)) return null;
  return (
    <Card id="league-captain" title="Against your league" eyebrow={data?.league_name ?? "Mini-league"} icon={<Trophy size={16} />} source={["official", "model"]}>
      {options.length > 1 ? (
        <label className="select-label league-captain-select">
          <span>League</span>
          <select value={leagueId ?? ""} onChange={(event) => setChosen(Number(event.target.value))}>
            {options.map((league) => <option key={league.league_id} value={league.league_id}>{league.name}</option>)}
          </select>
        </label>
      ) : null}
      {(leagues.loading && !leagues.data) || (captain.loading && !data) ? <Skeleton lines={4} /> : null}
      {captain.error && !data ? <DataState compact tone="error" title="League view is unavailable" action={<button className="btn btn-sm" onClick={captain.reload}>Try again</button>}>{captain.error}</DataState> : null}
      {data ? (
        <>
          <p className="league-mode">{data.mode.text}</p>
          {pick ? (
            <div className="league-pick">
              <span className="eyebrow">League pick</span>
              <strong>{pick.name}</strong>
              <small>{pick.reason}{pick.cost > 0.05 ? `; gives up ${fixed(pick.cost)} expected points` : ""}.</small>
            </div>
          ) : null}
          <ul className="league-cap-list">
            {data.candidates.map((candidate) => (
              <li key={candidate.player_id} className={candidate.player_id === pick?.player_id ? "is-pick" : undefined}>
                <div className="league-cap-head">
                  <b>{candidate.name}</b>
                  <span className={`pill ${KIND[candidate.kind].tone}`}>{KIND[candidate.kind].label}</span>
                </div>
                <p>
                  {fixed(candidate.expected)} <Term k="xp">xP</Term>, usually {Math.round(candidate.range.low)}–{Math.round(candidate.range.high)} points
                  {" "}({Math.round(candidate.range.haul_chance * 100)}% chance of 10+). {share(candidate, data.rivals)}.
                </p>
                <p className="faint">In his best week out of ten (captained), you gain about {signed(candidate.swing_high)} on the average rival.</p>
              </li>
            ))}
          </ul>
          <details className="card-more">
            <summary>How is this worked out?</summary>
            <p className="card-note">
              A captain is worth the same on average whoever else owns him; your league changes the risk. Captain the player most rivals captain and you move with them (safe).
              Captain one nobody else does and his score swings you against everyone (differential). Near the top it pays to match; far behind late in the season a
              differential can be worth a little expected points. Ranges come from what players with the same expected score actually scored in a backtest.
              {data.basis ? ` ${data.basis}` : ""}
            </p>
          </details>
        </>
      ) : null}
    </Card>
  );
}
