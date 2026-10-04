"use client";

import { Activity, ArrowRightLeft, Crown, Goal, Hourglass, Radio, Sparkles, Trophy } from "lucide-react";

import { Kit } from "@/components/kit/Kit";
import { FormationRows, PitchPlayer, PitchSurface } from "@/components/pitch/Pitch";
import { PlayerChip } from "@/components/player/PlayerChip";
import { Card, SourceBadge, Stat } from "@/components/ui/primitives";
import type { LiveEvent, LiveFixture } from "@/lib/contracts";
import { compact, fixed, plural, shortTime } from "@/lib/format";
import type { LiveView } from "@/lib/model/live";
import type { SourceKind } from "@/lib/model/phase";
import type { SquadPlayer } from "@/lib/model/squad";

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

export function LiveCockpit({ live, squad, source, overallRank, eventRank }: { live: LiveView; squad: SquadPlayer[]; source: SourceKind; overallRank: number | null; eventRank: number | null }) {
  const starters = squad.filter((player) => player.isStarter);
  const bench = squad.filter((player) => !player.isStarter).sort((left, right) => left.slot - right.slot);
  const totalActive = live.finished + live.playing + live.remaining + live.noFixture;
  const progress = totalActive ? (live.finished + live.playing * 0.5) / totalActive : 0;
  const totalActiveCount = live.finished + live.playing + live.remaining + live.noFixture;
  // Comparing a part-played Gameweek with a full-Gameweek projection would mislead, so the delta waits for the final whistle.
  const delta = live.playing === 0 && live.remaining === 0 && totalActiveCount > 0 && live.points != null && live.projectedXI != null ? live.points - live.projectedXI : null;
  const allDone = live.playing === 0 && live.remaining === 0;

  return (
    <div className="live-grid">
      <section className="live-hero card card-live" aria-labelledby="live-title">
        <header className="card-head">
          <div className="card-title"><span className="card-icon live-icon" aria-hidden="true"><Radio size={16} /></span><div><span className="eyebrow">Gameweek {live.event} · {allDone ? "all your matches played" : "in progress"}</span><h2 id="live-title">Live points</h2></div></div>
          <div className="card-meta"><SourceBadge kind={source} /></div>
        </header>
        <div className="live-hero-body">
          <div className="live-score">
            <strong className="num" aria-label={live.points == null ? "Live points unavailable" : `${live.points} live points`}>{live.points ?? "—"}</strong>
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
            <Stat size="sm" label={<><Crown size={12} aria-hidden="true" />Captain</>} value={live.captainContribution ?? "—"} unit="pts" sub={live.captain ? `${live.captain.name}${live.captain.multiplier && live.captain.multiplier > 2 ? " · triple" : ""}` : "No captain"} />
            <Stat size="sm" label="Bench" value={live.benchPoints ?? "—"} unit="pts" sub="Not counted unless auto-subbed" />
            <Stat size="sm" label="GW rank" value={compact(eventRank)} sub="Official, updates after matches" />
            <Stat size="sm" label="Overall" value={compact(overallRank)} sub="Official" />
          </div>
        </div>
      </section>

      <Card title="Your XI live" icon={<Activity size={16} />} source={source} className="live-pitch-card">
        <PitchSurface compact label="Starting eleven with live points">
          <FormationRows starters={starters} render={(player) => <PitchPlayer key={player.id} player={player} mode="live" size="sm" />} />
        </PitchSurface>
        <div className="bench bench-compact">
          <div className="bench-head"><span className="eyebrow">Bench</span></div>
          <div className="bench-row">{bench.map((player, index) => <PitchPlayer key={player.id} player={player} mode="live" size="sm" benchIndex={index} />)}</div>
        </div>
      </Card>

      <div className="live-side">
        <Card title="Your matches" icon={<Goal size={16} />} source={source}>
          {live.fixtures.length ? <ul className="scores">{live.fixtures.map((fixture) => <FixtureScore key={fixture.fixture_id} fixture={fixture} />)}</ul> : <p className="faint">No fixture data for your clubs yet.</p>}
        </Card>

        <Card title="What is happening" icon={<Sparkles size={16} />} source="derived">
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

        <Card title="Owned player returns" icon={<Activity size={16} />} source={source}>
          {live.events.length ? (
            <ul className="events">
              {live.events.slice(0, 10).map((event) => {
                const player = squad.find((item) => item.id === event.player_id);
                return (
                  <li key={`${event.player_id}-${event.event_type}`} className={NEGATIVE_EVENTS.has(event.event_type) ? "event-neg" : "event-pos"}>
                    <PlayerChip name={event.player_name} team={player?.team} teamShort={event.team_short} position={player?.position} size={26} meta={event.active ? "Starting XI" : "Bench"} />
                    <span className="event-label">{eventLabel(event)}{event.provisional ? <em>provisional</em> : null}</span>
                  </li>
                );
              })}
            </ul>
          ) : <p className="faint">No returns from your players yet.</p>}
          <p className="card-note">Official totals per player, not a minute-by-minute timeline. Bonus is provisional until FPL confirms it.</p>
        </Card>
      </div>
    </div>
  );
}
