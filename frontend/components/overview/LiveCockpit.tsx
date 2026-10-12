"use client";

import { Activity, ArrowRight, ArrowRightLeft, Crown, Goal, Hourglass, Radio, Sparkles, Trophy } from "lucide-react";

import { Kit } from "@/components/kit/Kit";
import { FormationRows, PitchPlayer, PitchSurface } from "@/components/pitch/Pitch";
import { PlayerChip } from "@/components/player/PlayerChip";
import { CountUp } from "@/components/ui/CountUp";
import { Card, SourceBadge, Stat } from "@/components/ui/primitives";
import type { LiveEvent, LiveFixture } from "@/lib/contracts";
import { compact, fixed, plural, shortTime } from "@/lib/format";
import type { LiveView } from "@/lib/model/live";
import type { SourceKind } from "@/lib/model/phase";
import type { SquadPlayer } from "@/lib/model/squad";
import { useCountUp, useMotionLevel } from "@/lib/motion";

const EVENT_COPY: Record<LiveEvent["event_type"], [string, string]> = {
  GOAL: ["goal", "goals"],
  ASSIST: ["assist", "assists"],
  PENALTY_SAVE: ["penalty save", "penalty saves"],
  SAVE: ["save", "saves"],
  BONUS: ["bonus point", "bonus points"],
  YELLOW_CARD: ["yellow card", "yellow cards"],
  RED_CARD: ["red card", "red cards"],
  OWN_GOAL: ["own goal", "own goals"],
  PENALTY_MISS: ["penalty miss", "penalty misses"],
};

const NEGATIVE_EVENTS = new Set<LiveEvent["event_type"]>(["YELLOW_CARD", "RED_CARD", "OWN_GOAL", "PENALTY_MISS"]);

export function eventLabel(event: LiveEvent) {
  const [singular, plural] = EVENT_COPY[event.event_type];
  return `${event.count} ${event.count === 1 ? singular : plural}`;
}

/** One row per player, keeping the feed's order of first appearance. */
export function groupEventsByPlayer(events: LiveEvent[]): Array<{ playerId: number; events: LiveEvent[] }> {
  const groups = new Map<number, LiveEvent[]>();
  for (const event of events) groups.set(event.player_id, [...(groups.get(event.player_id) ?? []), event]);
  return [...groups].map(([playerId, grouped]) => ({ playerId, events: grouped }));
}

function FixtureScore({ fixture }: { fixture: LiveFixture }) {
  const status = fixture.finished ? "FT" : fixture.started ? `${fixture.minutes}′` : shortTime(fixture.kickoff_time);
  const state = fixture.finished ? "ft" : fixture.started ? "live" : "pre";
  return (
    <li className={`score score-${state}`}>
      <span className="score-team"><Kit team={fixture.home_team} teamShort={fixture.home_team_short} size={22} bare /><b>{fixture.home_team_short ?? fixture.home_team}</b></span>
      <span className="score-mid num">{fixture.started ? `${fixture.home_score ?? 0} – ${fixture.away_score ?? 0}` : "v"}</span>
      <span className="score-team score-away"><b>{fixture.away_team_short ?? fixture.away_team}</b><Kit team={fixture.away_team} teamShort={fixture.away_team_short} size={22} bare /></span>
      <span className={`score-status score-status-${state}`}>{state === "live" ? <i aria-hidden="true" /> : null}{status}</span>
    </li>
  );
}

export type PlanPreview = { event: number | null; label: string; provisional: boolean; onOpen: () => void };

export function LiveCockpit({ live, squad, source, overallRank, eventRank, planPreview = null }: { live: LiveView; squad: SquadPlayer[]; source: SourceKind; overallRank: number | null; eventRank: number | null; planPreview?: PlanPreview | null }) {
  const starters = squad.filter((player) => player.isStarter);
  const bench = squad.filter((player) => !player.isStarter).sort((left, right) => left.slot - right.slot);
  const totalActive = live.finished + live.playing + live.remaining + live.noFixture;
  const progress = totalActive ? (live.finished + live.playing * 0.5) / totalActive : 0;
  const totalActiveCount = live.finished + live.playing + live.remaining + live.noFixture;
  // Comparing a part-played Gameweek with a full-Gameweek projection would mislead, so the delta waits for the final whistle.
  const delta = live.playing === 0 && live.remaining === 0 && totalActiveCount > 0 && live.points != null && live.projectedXI != null ? live.points - live.projectedXI : null;
  const allDone = live.playing === 0 && live.remaining === 0;
  // The big numbers count up when the cockpit opens and whenever they move.
  const motion = useMotionLevel();
  const shownPoints = useCountUp(live.points, motion, { fromZero: true, duration: 900 });
  const shownCaptain = useCountUp(live.captainContribution, motion, { fromZero: true });
  const liveMatches = live.fixtures.filter((fixture) => fixture.started && !fixture.finished).length;
  const finishedMatches = live.fixtures.filter((fixture) => fixture.finished).length;
  const upcomingMatches = live.fixtures.length - liveMatches - finishedMatches;
  const returnsCount = groupEventsByPlayer(live.events).length;

  return (
    <div className="live-grid">
      <section className="live-hero card card-live" aria-labelledby="live-title">
        <header className="card-head">
          <div className="card-title"><span className="card-icon live-icon" aria-hidden="true"><Radio size={16} /></span><div><span className="eyebrow">Gameweek {live.event} · {allDone ? "all your matches played" : "in progress"}</span><h2 id="live-title">Live points</h2></div></div>
          <div className="card-meta"><SourceBadge kind={source} /></div>
        </header>
        <div className="live-hero-body">
          <div className="live-score">
            <strong className="num" aria-label={live.points == null ? "Live points unavailable" : `${live.points} live points`}>{shownPoints == null ? "—" : Math.round(shownPoints)}</strong>
            <span className="live-score-context">
              {live.projectedXI != null ? <>Model expected <b className="tone-accent">{fixed(live.projectedXI)} xP</b> for your active picks <SourceBadge kind="model" /></> : "Model expectation unavailable"}
              {delta != null ? <span className={delta >= 0 ? "tone-pos" : "tone-neg"}> · {delta >= 0 ? "+" : "−"}{Math.abs(delta).toFixed(1)} vs expected</span> : null}
            </span>
          </div>
          <div className="live-progress" aria-label={`${live.finished} finished, ${live.playing} playing, ${live.remaining} still to play`}>
            <div className="live-bar" aria-hidden="true">
              <i className="live-bar-done" style={{ flex: live.finished }} />
              <i className="live-bar-now" style={{ flex: live.playing }} />
              <i className="live-bar-left" style={{ flex: live.remaining + live.noFixture }} />
            </div>
            <div className="live-legend">
              <span><i className="dot dot-ok" />{live.finished} played</span>
              <span><i className="dot live-dot" />{live.playing} playing</span>
              <span><i className="dot dot-unknown" />{live.remaining} to play</span>
              {live.noFixture ? <span className="faint">{live.noFixture} without a match</span> : null}
            </div>
            <span className="sr-only">{Math.round(progress * 100)}% of starter minutes resolved</span>
          </div>
          <div className="live-stats">
            <Stat size="sm" label={<><Crown size={12} aria-hidden="true" />Captain</>} value={shownCaptain == null ? "—" : Math.round(shownCaptain)} unit="pts" sub={live.captain ? `${live.captain.name}${live.captain.multiplier && live.captain.multiplier > 2 ? " · triple" : ""}` : "No captain"} />
            <Stat size="sm" label="Bench" value={<CountUp value={live.benchPoints} />} unit="pts" sub="Not counted unless auto-subbed" />
            <Stat size="sm" label="GW rank" value={compact(eventRank)} sub="Official, updates after matches" />
            <Stat size="sm" label="Overall" value={compact(overallRank)} sub="From FPL" />
          </div>
        </div>
      </section>

      {planPreview ? (
        <button type="button" className="preview-line preview-plan" onClick={planPreview.onOpen}>
          <span><b>GW{planPreview.event ?? "—"} plan</b> · {planPreview.label}{planPreview.provisional ? " (provisional)" : ""}</span>
          <span className="preview-cta">Open plan<ArrowRight size={14} aria-hidden="true" /></span>
        </button>
      ) : null}

      <Card title="Your XI live" icon={<Activity size={16} />} source={source} className="live-pitch-card"
        collapse={{ id: "xi-live", defaults: { mobile: true, desktop: true }, summary: `${starters.length} starters · ${live.points ?? "—"} pts` }}>
        <PitchSurface compact label="Starting eleven with live points">
          <FormationRows starters={starters} render={(player) => <PitchPlayer key={player.id} player={player} mode="live" size="sm" />} />
        </PitchSurface>
        <div className="bench bench-compact">
          <div className="bench-head"><span className="eyebrow">Bench</span></div>
          <div className="bench-row">{bench.map((player, index) => <PitchPlayer key={player.id} player={player} mode="live" size="sm" benchIndex={index} />)}</div>
        </div>
        <div className="live-key" aria-hidden="true">
          <span><i className="key-playing" />Playing</span>
          <span><i className="key-finished" />Finished</span>
          <span><i className="key-upcoming" />To play</span>
        </div>
      </Card>

      <div className="live-side">
        <Card title="Your matches" icon={<Goal size={16} />} source={source}
          collapse={{ id: "matches", defaults: { mobile: false, desktop: true }, summary: `${liveMatches} live · ${finishedMatches} finished · ${upcomingMatches} to play` }}>
          {live.fixtures.length ? <ul className="scores">{live.fixtures.map((fixture) => <FixtureScore key={fixture.fixture_id} fixture={fixture} />)}</ul> : <p className="faint">No fixture data for your clubs yet.</p>}
        </Card>

        <Card title="What is happening" icon={<Sparkles size={16} />} source="derived"
          collapse={{
            id: "happening",
            defaults: { mobile: false, desktop: true },
            summary: live.yetToPlay.length ? `${plural(live.yetToPlay.length, "starter")} still to finish` : "All your starters have finished",
            // A possible auto-sub opens this section until it is closed.
            signal: live.autoSubWatch.length ? `autosub:${live.event}:${live.autoSubWatch.map(({ out }) => out.id).join("-")}` : null,
          }}>
          <ul className="insights">
            {live.topContributors[0] && (live.topContributors[0].liveContribution ?? 0) > 0 ? (
              <li><Trophy size={15} aria-hidden="true" className="tone-pos" /><span><b>{live.topContributors[0].name}</b> leads your team with {live.topContributors[0].liveContribution} pts{live.topContributors[0].isCaptain ? " (captained)" : ""}.</span></li>
            ) : null}
            {live.yetToPlay.length ? (
              <li><Hourglass size={15} aria-hidden="true" className="tone-accent" /><span>{plural(live.yetToPlay.length, "starter")} still to finish: {live.yetToPlay.map((player) => player.name).join(", ")}.</span></li>
            ) : <li><Hourglass size={15} aria-hidden="true" /><span>All your starters have finished or have no match.</span></li>}
            {live.autoSubWatch.map(({ out, in: incoming }) => (
              <li key={out.id}><ArrowRightLeft size={15} aria-hidden="true" className="tone-warn" /><span><b>{out.name}</b> played 0 minutes.{incoming ? <> If FPL auto-subs, <b>{incoming.name}</b> is first in your bench order who fits the formation.</> : " No eligible bench player fits the formation."}</span></li>
            ))}
          </ul>
        </Card>

        <Card title="Owned player returns" icon={<Activity size={16} />} source={source}
          collapse={{ id: "returns", defaults: { mobile: false, desktop: true }, summary: returnsCount ? `${plural(returnsCount, "player")} with returns` : "No returns yet" }}>
          {live.events.length ? (
            <ul className="events">
              {groupEventsByPlayer(live.events).slice(0, 10).map(({ playerId, events }) => {
                const first = events[0];
                const player = squad.find((item) => item.id === playerId);
                const negative = events.every((event) => NEGATIVE_EVENTS.has(event.event_type));
                return (
                  <li key={playerId} className={negative ? "event-neg" : "event-pos"}>
                    <PlayerChip name={first.player_name} team={player?.team} teamShort={first.team_short} position={player?.position} size={26} meta={first.active ? "Starting XI" : "Bench"} />
                    <span className="event-label">
                      {events.map((event) => (
                        <span key={event.event_type} className={NEGATIVE_EVENTS.has(event.event_type) ? "tone-neg" : undefined}>
                          {eventLabel(event)}
                        </span>
                      ))}
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : <p className="faint">No returns from your players yet.</p>}
          <p className="card-note">Official totals per player, not a minute-by-minute timeline.</p>
        </Card>
      </div>
    </div>
  );
}
