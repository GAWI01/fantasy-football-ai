"use client";

import { ArrowRight, BrainCircuit, Crown, History, LineChart, Timer } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { useTeam } from "@/app/providers/TeamProvider";
import { TrendChart } from "@/components/charts/TrendChart";
import { DataState } from "@/components/states/DataState";
import { CountUp } from "@/components/ui/CountUp";
import { Card, Delta, SourceBadge, SourceScope, Skeleton, Stat } from "@/components/ui/primitives";
import type { RankHistoryItem, ReviewData } from "@/lib/contracts";
import { compact, fixed, signed } from "@/lib/format";
import { useReview } from "@/lib/hooks/data";

const OUTCOME: Record<string, { label: string; tone: string }> = {
  ABOVE_EXPECTATION: { label: "Beat the model", tone: "pos" },
  IN_LINE: { label: "In line with the model", tone: "neutral" },
  BELOW_EXPECTATION: { label: "Below the model", tone: "neg" },
};

const QUALITY: Record<string, { label: string; tone: string }> = {
  SOUND: { label: "Sound process", tone: "pos" },
  MARGINAL: { label: "Marginal process", tone: "warn" },
  QUESTIONABLE: { label: "Process to review", tone: "neg" },
};

function SeasonSummary({ history }: { history: RankHistoryItem[] }) {
  const ranked = history.filter((item) => item.overall_rank);
  const last = history[history.length - 1];
  const best = history.reduce<RankHistoryItem | null>((top, item) => (!top || item.points > top.points ? item : top), null);
  const average = history.length ? history.reduce((total, item) => total + item.points, 0) / history.length : null;
  const transfers = history.reduce((total, item) => total + (item.transfers ?? 0), 0);
  const firstRank = ranked[0]?.overall_rank ?? null;
  const lastRank = ranked[ranked.length - 1]?.overall_rank ?? null;
  return (
    <>
      <SourceScope kinds={["official"]}>
      <div className="stat-row has-source">
        <span className="stat-row-source"><SourceBadge kind="official" pinned /></span>
        <Stat label="Total points" value={<CountUp value={last?.total_points} format={(n) => n.toLocaleString("en-GB")} />} source="official" size="lg" />
        <Stat label="Overall rank" value={compact(lastRank)} source="official" size="lg" sub={firstRank && lastRank && ranked.length > 1 ? `${lastRank < firstRank ? "Up" : lastRank > firstRank ? "Down" : "Level"} from ${compact(firstRank)} in GW${ranked[0].event}` : undefined} />
        <Stat label="Average GW" value={<CountUp value={average} decimals={1} />} source="derived" size="lg" />
        <Stat label="Best GW" value={best ? <CountUp value={best.points} /> : "—"} sub={best ? `GW${best.event}` : undefined} source="official" size="lg" />
        <Stat label="Transfers made" value={history.some((item) => item.transfers != null) ? <CountUp value={transfers} /> : "—"} source="official" size="lg" />
      </div>
      </SourceScope>
      <div className="grid-2">
        <Card title="Overall rank" icon={<LineChart size={16} />} source="official">
          {ranked.length > 1 ? (
            <TrendChart label="Overall rank by Gameweek (lower is better)" points={ranked.map((item) => ({ x: item.event, y: item.overall_rank as number }))} invert yLabel={(value) => compact(value)} />
          ) : <p className="faint">Rank history appears after two Gameweeks.</p>}
        </Card>
        <Card title="Points per Gameweek" icon={<History size={16} />} source="official">
          {history.length ? (
            <TrendChart label="Official points per Gameweek" kind="bar" tone="live" points={history.map((item) => ({ x: item.event, y: item.points }))} reference={average != null ? { y: average, label: `Your average ${fixed(average, 1)}` } : undefined} />
          ) : <p className="faint">No Gameweeks played yet.</p>}
        </Card>
      </div>
    </>
  );
}

function ReviewBody({ data }: { data: Extract<ReviewData, { available: true }> }) {
  const outcome = OUTCOME[data.summary.outcome] ?? { label: data.summary.outcome, tone: "neutral" };
  const quality = QUALITY[data.decision_quality.label] ?? QUALITY.QUESTIONABLE;
  const picks = [...data.picks].sort((left, right) => left.slot - right.slot);
  return (
    <div className="stack">
      <Card className="review-hero" title={`GW${data.event} against the model`} source={["official", "model"]} tone="accent">
        <div className="review-scoreline">
          <Stat label="Model projected" value={<CountUp value={data.summary.projected_points} decimals={1} />} source="model" size="xl" />
          <ArrowRight className="faint" aria-hidden="true" />
          <Stat label="Official points" value={<CountUp value={data.summary.official_points} />} source="official" size="xl" />
          <div className={`review-outcome tone-${outcome.tone}`}>
            <span className="eyebrow">Versus model</span>
            <strong className="num"><Delta value={data.summary.actual_vs_projected} /></strong>
            <span>{outcome.label}</span>
          </div>
        </div>
        <p className="card-note">Hit cost {data.summary.hit_cost} pts · net after hits {data.summary.net_points_after_hits} pts. The projection is the model file saved before the deadline ({data.prediction_version}); it is never regenerated after the fact.</p>
      </Card>

      {data.next_signals.length ? (
        <Card title="Signals for next Gameweek" icon={<BrainCircuit size={16} />} source="derived" action={<Link className="link" href="/plan">Open plan</Link>}>
          <ul className="insight-list">
            {data.next_signals.map((signal) => (
              <li key={signal.type} className={signal.severity === "ACTION" ? "insight-warn" : undefined}>
                <span className={`pill ${signal.severity === "ACTION" ? "pill-warn" : ""}`}>{signal.severity === "ACTION" ? "Act" : "Watch"}</span>
                <div><strong>{signal.title}</strong><p>{signal.message}</p></div>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card title="Your calls" icon={<Crown size={16} />} source={["official", "model"]}>
        <div className="review-tiles">
          <div className="review-call">
            <span className="eyebrow">Captain</span>
            {data.captain ? (
              <>
                <strong>{data.captain.name}</strong>
                <span className="faint">{data.captain.multiplier}× armband · {data.captain.actual_contribution} pts (model {fixed(data.captain.projected_contribution)})</span>
                <span><Delta value={data.captain.contribution_delta} /> vs model</span>
              </>
            ) : <span className="faint">Captain history was not available.</span>}
          </div>
          <div className="review-call">
            <span className="eyebrow">Decisions</span>
            <strong className={`tone-${quality.tone}`}>{quality.label}</strong>
            <span className="faint">Transfers {signed(data.decision_quality.projected_transfer_value)} · captain cost {signed(-data.decision_quality.captain_opportunity_cost)} xP</span>
            <span className="faint">Judged on the forecast before the deadline, so luck does not count.</span>
          </div>
          <div className="review-call">
            <span className="eyebrow">Bench</span>
            <strong>{data.bench.official_points} pts on the bench</strong>
            <span className="faint">{data.bench.player_count} players · model had {fixed(data.bench.projected_points)} xP</span>
          </div>
        </div>
      </Card>

      <Card title="Biggest surprises" icon={<Timer size={16} />} source="model">
        <div className="review-tiles review-tiles-2">
          <div className="review-call">
            <span className="eyebrow">Points</span>
            <strong>{data.largest_model_miss.name}</strong>
            <span className="faint">Model {fixed(data.largest_model_miss.predicted_points)} · scored {data.largest_model_miss.actual_points}</span>
            <span><Delta value={data.largest_model_miss.residual} /> vs model</span>
          </div>
          <div className="review-call">
            <span className="eyebrow">Minutes</span>
            {data.largest_xmins_miss ? (
              <>
                <strong>{data.largest_xmins_miss.name}</strong>
                <span className="faint">Forecast {Math.round(data.largest_xmins_miss.predicted_xmins)}′ · played {data.largest_xmins_miss.actual_minutes}′</span>
                <span><Delta value={data.largest_xmins_miss.residual} digits={0} /> minutes</span>
              </>
            ) : <span className="faint">This saved model file predates the minutes forecast.</span>}
          </div>
        </div>
      </Card>

      {data.transfers.length ? (
        <Card title="Transfers" icon={<ArrowRight size={16} />} source="derived"
          collapse={{ id: "review-transfers", defaults: { mobile: false, desktop: false }, summary: `${data.transfers.length} transfer${data.transfers.length === 1 ? "" : "s"} · model ${signed(data.transfers.reduce((total, item) => total + item.projected_delta, 0))}, actual ${signed(data.transfers.reduce((total, item) => total + item.actual_delta, 0))}` }}>
          <ul className="plain-list">
            {data.transfers.map((transfer) => (
              <li key={`${transfer.player_out.player_id}-${transfer.player_in.player_id}`}>
                <b>{transfer.player_out.name}</b> → <b>{transfer.player_in.name}</b>
                <span className="faint"> · model <Delta value={transfer.projected_delta} />, actual <Delta value={transfer.actual_delta} /></span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {picks.length ? (
        <Card title="Player by player" source={["official", "model"]} collapse={{ id: "review-players", defaults: { mobile: false, desktop: false }, summary: "Forecast and points for each of your 15" }}>
          <div className="table-wrap">
            <table className="table">
              <caption className="sr-only">Projected and actual points for each pick in GW{data.event}</caption>
              <thead><tr><th scope="col">Player</th><th scope="col" className="num">Projected</th><th scope="col" className="num">Actual</th><th scope="col" className="num">Residual</th></tr></thead>
              <tbody>
                {picks.map((pick) => (
                  <tr key={pick.player_id} className={pick.multiplier === 0 ? "is-bench" : undefined}>
                    <th scope="row">
                      <span className="cell-name">{pick.name}{pick.is_captain ? <span className="badge-c" aria-label="Captain">C</span> : pick.is_vice_captain ? <span className="badge-v" aria-label="Vice-captain">V</span> : null}</span>
                      <small className="faint">{pick.position} · {pick.team_short}{pick.multiplier === 0 ? " · bench" : ""}</small>
                    </th>
                    <td className="num tone-accent">{fixed(pick.projected_contribution)}</td>
                    <td className="num"><b>{pick.actual_contribution}</b></td>
                    <td className="num"><Delta value={pick.actual_contribution - pick.projected_contribution} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

    </div>
  );
}

/** Season history plus a per-Gameweek review against the saved pre-deadline model. */
export function ReviewWorkspace() {
  const { ready, teamId, dashboard, loading, error, refresh } = useTeam();
  const history = useMemo(() => dashboard?.data.history?.history ?? [], [dashboard]);
  const [event, setEvent] = useState<number | undefined>(undefined);
  const review = useReview(teamId, event);

  if (!ready || (!dashboard && loading)) return <DataState title="Loading your team…" loading>Fetching your official history before building the review.</DataState>;
  if (!dashboard && teamId && error) return <DataState tone="error" title="Your team could not be loaded" action={<button className="btn btn-sm btn-primary" onClick={() => void refresh()}>Try again</button>}>{error}</DataState>;
  if (!teamId || !dashboard) return <DataState tone="empty" title="Connect a team first" action={<Link className="btn btn-sm btn-primary" href="/">Connect your team</Link>}>History and reviews use your public FPL Team ID.</DataState>;

  const reviewData = review.data?.data;
  const events = history.map((item) => item.event).reverse();
  const selected = event ?? reviewData?.event;

  return (
    <div className="stack">
      <header className="page-head">
        <div>
          <span className="eyebrow">Season record</span>
          <h1>History &amp; Review</h1>
          <p className="page-lede">Official results set against what the model said before each deadline.</p>
        </div>
      </header>

      {dashboard.data.history ? <SeasonSummary history={history} /> : <DataState tone="unavailable" compact title="Season history unavailable">FPL did not return manager history on the last refresh.</DataState>}

      <section className="stack" aria-labelledby="review-title">
        <div className="section-head">
          <h2 id="review-title">Gameweek review <SourceBadge kind="derived" /></h2>
          {events.length ? (
            <label className="select-label">
              <span>Gameweek</span>
              <select value={selected ?? ""} onChange={(changeEvent) => setEvent(Number(changeEvent.target.value))}>
                {events.map((value) => <option key={value} value={value}>GW{value}</option>)}
              </select>
            </label>
          ) : null}
        </div>
        {review.loading && !review.data ? <Card><Skeleton lines={6} /></Card> : review.error && !review.data ? (
          <DataState tone="error" title="Review could not be loaded" action={<button className="btn btn-sm" onClick={review.reload}>Try again</button>}>{review.error}</DataState>
        ) : reviewData && !reviewData.available ? (
          <DataState tone="unavailable" title={`No review for GW${reviewData.event}`}>{reviewData.reason} Pick another Gameweek above. Forecasts are never rebuilt after the fact, so every review is a fair test.</DataState>
        ) : reviewData ? (
          <>
            {review.data?.meta.stale ? <DataState tone="stale" compact title="Official outcomes may be cached">The saved model file is unchanged; official points may lag the latest FPL update.</DataState> : null}
            <ReviewBody data={reviewData} />
          </>
        ) : null}
      </section>
    </div>
  );
}
