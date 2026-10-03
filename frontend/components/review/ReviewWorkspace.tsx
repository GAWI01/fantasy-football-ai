"use client";

import { ArrowRight, BrainCircuit, Crown, History, LineChart, ShieldCheck, Timer } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { useTeam } from "@/app/providers/TeamProvider";
import { TrendChart } from "@/components/charts/TrendChart";
import { DataState } from "@/components/states/DataState";
import { Card, Delta, SourceBadge, Skeleton, Stat } from "@/components/ui/primitives";
import type { RankHistoryItem, ReviewData } from "@/lib/contracts";
import { compact, fixed, integer, signed } from "@/lib/format";
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
      <div className="stat-row">
        <Stat label="Total points" value={integer(last?.total_points ?? null)} source="official" size="lg" />
        <Stat label="Overall rank" value={compact(lastRank)} source="official" size="lg" sub={firstRank && lastRank && ranked.length > 1 ? `${lastRank < firstRank ? "Up" : lastRank > firstRank ? "Down" : "Level"} from ${compact(firstRank)} in GW${ranked[0].event}` : undefined} />
        <Stat label="Average GW" value={fixed(average, 1)} source="derived" size="lg" />
        <Stat label="Best GW" value={best ? best.points : "—"} sub={best ? `GW${best.event}` : undefined} source="official" size="lg" />
        <Stat label="Transfers made" value={history.some((item) => item.transfers != null) ? transfers : "—"} source="official" size="lg" />
      </div>
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
          <Stat label="Model projected" value={fixed(data.summary.projected_points)} source="model" size="xl" />
          <ArrowRight className="faint" aria-hidden="true" />
          <Stat label="Official points" value={data.summary.official_points} source="official" size="xl" />
          <div className={`review-outcome tone-${outcome.tone}`}>
            <span className="eyebrow">Versus model</span>
            <strong className="num"><Delta value={data.summary.actual_vs_projected} /></strong>
            <span>{outcome.label}</span>
          </div>
        </div>
        <p className="card-note">Hit cost {data.summary.hit_cost} pts · net after hits {data.summary.net_points_after_hits} pts. The projection is the model file saved before the deadline ({data.prediction_version}); it is never regenerated after the fact.</p>
      </Card>

      <div className="grid-3">
        <Card title="Captain" icon={<Crown size={16} />} source="official">
          {data.captain ? (
            <div className="review-call">
              <strong>{data.captain.name}</strong>
              <span className="faint">{data.captain.multiplier}× armband</span>
              <dl className="mini-dl">
                <div><dt>Projected</dt><dd>{fixed(data.captain.projected_contribution)}</dd></div>
                <div><dt>Actual</dt><dd>{data.captain.actual_contribution}</dd></div>
                <div><dt>Delta</dt><dd><Delta value={data.captain.contribution_delta} /></dd></div>
              </dl>
            </div>
          ) : <p className="faint">Captain history was not available.</p>}
        </Card>
        <Card title="Decision quality" icon={<ShieldCheck size={16} />} source="model">
          <div className="review-call">
            <strong className={`tone-${quality.tone}`}>{quality.label}</strong>
            <span className="faint">{signed(data.decision_quality.projected_decision_value)} projected decision value</span>
            <dl className="mini-dl">
              <div><dt>Transfers</dt><dd>{signed(data.decision_quality.projected_transfer_value)}</dd></div>
              <div><dt>Captain cost</dt><dd>{signed(-data.decision_quality.captain_opportunity_cost)}</dd></div>
            </dl>
            <p className="card-note">Rated on pre-deadline projections only. Luck after the deadline does not change it.</p>
          </div>
        </Card>
        <Card title="Bench" icon={<History size={16} />} source="official">
          <div className="review-call">
            <strong>{data.bench.official_points} pts on the bench</strong>
            <span className="faint">{data.bench.player_count} players · model had {fixed(data.bench.projected_points)} xP</span>
          </div>
        </Card>
      </div>

      <div className="grid-3">
        <Card title="Transfers" icon={<ArrowRight size={16} />} source="derived">
          {data.transfers.length ? (
            <ul className="plain-list">
              {data.transfers.map((transfer) => (
                <li key={`${transfer.player_out.player_id}-${transfer.player_in.player_id}`}>
                  <b>{transfer.player_out.name}</b> → <b>{transfer.player_in.name}</b>
                  <span className="faint"> · model <Delta value={transfer.projected_delta} />, actual <Delta value={transfer.actual_delta} /></span>
                </li>
              ))}
            </ul>
          ) : <p className="faint">No transfers this Gameweek.</p>}
        </Card>
        <Card title="Biggest model miss" icon={<BrainCircuit size={16} />} source="model">
          <div className="review-call">
            <strong>{data.largest_model_miss.name}</strong>
            <dl className="mini-dl">
              <div><dt>Projected</dt><dd>{fixed(data.largest_model_miss.predicted_points)}</dd></div>
              <div><dt>Actual</dt><dd>{data.largest_model_miss.actual_points}</dd></div>
              <div><dt>Residual</dt><dd><Delta value={data.largest_model_miss.residual} /></dd></div>
            </dl>
          </div>
        </Card>
        <Card title="Biggest minutes miss" icon={<Timer size={16} />} source="model">
          {data.largest_xmins_miss ? (
            <div className="review-call">
              <strong>{data.largest_xmins_miss.name}</strong>
              <dl className="mini-dl">
                <div><dt>Forecast</dt><dd>{Math.round(data.largest_xmins_miss.predicted_xmins)}′</dd></div>
                <div><dt>Played</dt><dd>{data.largest_xmins_miss.actual_minutes}′</dd></div>
                <div><dt>Residual</dt><dd><Delta value={data.largest_xmins_miss.residual} digits={0} /></dd></div>
              </dl>
            </div>
          ) : <p className="faint">This saved model file predates the minutes forecast, so no minutes review is possible.</p>}
        </Card>
      </div>

      {picks.length ? (
        <Card title="Player by player" source={["official", "model"]}>
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

      <Card title="Signals for next Gameweek" icon={<BrainCircuit size={16} />} source="derived" action={<Link className="link" href="/plan">Open plan</Link>}>
        {data.next_signals.length ? (
          <ul className="insight-list">
            {data.next_signals.map((signal) => (
              <li key={signal.type} className={signal.severity === "ACTION" ? "insight-warn" : undefined}>
                <span className={`pill ${signal.severity === "ACTION" ? "pill-warn" : ""}`}>{signal.severity === "ACTION" ? "Act" : "Watch"}</span>
                <div><strong>{signal.title}</strong><p>{signal.message}</p></div>
              </li>
            ))}
          </ul>
        ) : <p className="faint">No process signal cleared the evidence threshold.</p>}
      </Card>
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
          <DataState tone="unavailable" title={`GW${reviewData.event} review unavailable`}>{reviewData.reason} The model never rebuilds a model opinion that was not saved before the deadline.</DataState>
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
