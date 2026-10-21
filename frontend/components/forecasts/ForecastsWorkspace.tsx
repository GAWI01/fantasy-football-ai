"use client";

import { ChartColumnBig, ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

import { Kit } from "@/components/kit/Kit";
import { PageLinkTabs } from "@/components/shell/PageTabs";
import { DataState } from "@/components/states/DataState";
import { Card, Skeleton, SourceBadge } from "@/components/ui/primitives";
import type { MatchForecast, MatchForecastBacktest } from "@/lib/contracts";
import { useMatchForecasts } from "@/lib/hooks/data";

const pct = (value: number) => `${Math.round(value * 100)}%`;

function kickoff(value: string | null): string {
  if (!value) return "Kickoff to be confirmed";
  return new Date(value).toLocaleString([], { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });
}

/** Home win, draw and away win as one bar. */
function ResultBar({ forecast }: { forecast: MatchForecast }) {
  const { home, draw, away } = forecast.result;
  return (
    <div className="fc-result" role="img" aria-label={`${forecast.home.short} win ${pct(home)}, draw ${pct(draw)}, ${forecast.away.short} win ${pct(away)}`}>
      <div className="fc-bar" aria-hidden="true">
        <i className="fc-home" style={{ width: `${home * 100}%` }} />
        <i className="fc-draw" style={{ width: `${draw * 100}%` }} />
        <i className="fc-away" style={{ width: `${away * 100}%` }} />
      </div>
      <div className="fc-bar-labels" aria-hidden="true">
        <span><b className="num">{pct(home)}</b> {forecast.home.short}</span>
        <span><b className="num">{pct(draw)}</b> Draw</span>
        <span>{forecast.away.short} <b className="num">{pct(away)}</b></span>
      </div>
    </div>
  );
}

function Rough() {
  return <small className="fc-rough" title="In the test on past seasons this was no better than the season average">rough</small>;
}

function ForecastCard({ forecast }: { forecast: MatchForecast }) {
  const top = forecast.likely_scores[0];
  return (
    <article className="fc-card">
      <header className="fc-head">
        <span className="muted">{forecast.finished ? "Full time" : forecast.started ? "Playing now" : kickoff(forecast.kickoff_time)}</span>
      </header>
      <div className="fc-teams">
        <span className="fc-team"><Kit team={forecast.home.name ?? undefined} teamShort={forecast.home.short ?? undefined} size={34} /><b>{forecast.home.name}</b></span>
        <span className="fc-score num">{forecast.score ? `${forecast.score.home}–${forecast.score.away}` : "v"}</span>
        <span className="fc-team fc-team-away"><b>{forecast.away.name}</b><Kit team={forecast.away.name ?? undefined} teamShort={forecast.away.short ?? undefined} size={34} /></span>
      </div>
      <ResultBar forecast={forecast} />
      <dl className="fc-facts">
        <div><dt>Expected goals</dt><dd className="num">{forecast.expected_goals.home.toFixed(1)} – {forecast.expected_goals.away.toFixed(1)}</dd></div>
        {top ? <div><dt>Most likely score</dt><dd className="num">{top.home}–{top.away} <small className="muted">({pct(top.probability)})</small></dd></div> : null}
        <div><dt>Both score <Rough /></dt><dd className="num">{pct(forecast.both_teams_score)}</dd></div>
        <div><dt>Over 2.5 goals <Rough /></dt><dd className="num">{pct(forecast.total_goals_over["2.5"])}</dd></div>
        <div className="fc-wide"><dt>Clean sheet</dt><dd className="num">{forecast.home.short} {pct(forecast.clean_sheet.home)} · {forecast.away.short} {pct(forecast.clean_sheet.away)}</dd></div>
      </dl>
    </article>
  );
}

function HowGood({ backtest }: { backtest: MatchForecastBacktest | null }) {
  if (!backtest) return null;
  const seasons = `${backtest.seasons[0]} to ${backtest.seasons.at(-1)}`;
  return (
    <details className="card-more fc-howgood">
      <summary>How good is this?</summary>
      <p>
        Tested on {backtest.matches.toLocaleString()} past Premier League matches ({seasons}), forecasting each Gameweek from earlier matches only.
      </p>
      <ul>
        <li><b>Result:</b> the most likely outcome was right {pct(backtest.result.hit_rate_model)} of the time, and the chances beat the season averages. A side given 60% won about 60% of the time.</li>
        <li><b>Both teams score and over 2.5 goals:</b> no better than the season average, so they are marked <i>rough</i>. Goals are hard to call from expected goals alone.</li>
      </ul>
      <p className="muted">Early in a season, with few matches played, every forecast leans towards the league average.</p>
    </details>
  );
}

export function ForecastsWorkspace() {
  const [event, setEvent] = useState<number | null>(null);
  const forecasts = useMatchForecasts(event);
  const data = forecasts.data?.data;
  const shown = event ?? data?.event ?? null;
  // Forecasts use the data known today, so a past Gameweek would be judged
  // with hindsight: only the next Gameweek and later ones are offered.
  const first = data?.next_event ?? data?.current_event ?? 1;

  return (
    <div className="stack forecasts-page">
      <PageLinkTabs parent="players" label="Explore" />
      <header className="page-head">
        <div>
          <span className="eyebrow">Explore · Matches</span>
          <h1>Match forecasts</h1>
          <p className="page-lede">The model&apos;s chances for every match, from each club&apos;s expected goals. A forecast to read, not betting advice: no odds and no bookmakers.</p>
        </div>
        <div className="page-head-actions"><SourceBadge kind="model" /></div>
      </header>

      <div className="fc-stepper" role="group" aria-label="Gameweek">
        <button type="button" className="icon-btn" aria-label="Previous Gameweek" disabled={!shown || shown <= first} onClick={() => shown && setEvent(shown - 1)}><ChevronLeft size={18} aria-hidden="true" /></button>
        <b className="num">{shown ? `Gameweek ${shown}` : "Gameweek"}</b>
        <button type="button" className="icon-btn" aria-label="Next Gameweek" disabled={!shown || shown >= 38} onClick={() => shown && setEvent(shown + 1)}><ChevronRight size={18} aria-hidden="true" /></button>
      </div>

      {forecasts.error && !data ? <DataState tone="error" title="Match forecasts are unavailable" action={<button className="btn btn-sm" onClick={forecasts.reload}>Try again</button>}>{forecasts.error}</DataState> : null}

      <Card icon={<ChartColumnBig size={16} />} title={shown ? `Gameweek ${shown} matches` : "Matches"} source="model">
        {forecasts.loading && !data ? <Skeleton lines={8} /> : !data?.fixtures.length ? (
          <DataState tone="empty" compact title="No matches">No fixtures are scheduled for this Gameweek yet.</DataState>
        ) : (
          <div className="fc-list">{data.fixtures.map((forecast) => <ForecastCard key={forecast.fixture_id ?? `${forecast.home.id}-${forecast.away.id}`} forecast={forecast} />)}</div>
        )}
        <HowGood backtest={data?.backtest ?? null} />
      </Card>
    </div>
  );
}
