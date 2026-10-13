"use client";

import { ArrowDown, ArrowUp, Lock, Search, TrendingUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useTeam } from "@/app/providers/TeamProvider";
import { PlayerChip } from "@/components/player/PlayerChip";
import { PageLinkTabs } from "@/components/shell/PageTabs";
import { PriceSwapsCard } from "@/components/prices/PriceSwapsCard";
import { DataState } from "@/components/states/DataState";
import { Card, Segmented, Skeleton, SourceBadge } from "@/components/ui/primitives";
import type { PriceChangePlayer } from "@/lib/contracts";
import { price } from "@/lib/format";
import { countdown, isDrop, isRise, nextStatus, PRICE_STATUS_LABEL, statusFromLikelihood, type PriceStatus } from "@/lib/fpl/prices";
import { normalizePosition } from "@/lib/fpl/rules";
import { usePriceChanges } from "@/lib/hooks/data";

type Filter = "both" | "rise" | "drop";

/** Ticks once a second for the countdown. */
function useNow() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}

function StatusPill({ status }: { status: PriceStatus }) {
  return (
    <span className={`price-status price-status-${status}`}>
      {status === "locked" ? <Lock size={11} aria-hidden="true" /> : null}
      {PRICE_STATUS_LABEL[status]}
    </span>
  );
}

/** Progress towards the next change, from -100% (fall due) through 0 to +100% (rise due). */
function ProgressBar({ player }: { player: PriceChangePlayer }) {
  const value = player.percent ?? 0;
  const width = Math.min(100, Math.abs(value)) / 2;
  const trend = player.hourly_rate ?? 0;
  return (
    <span className="price-progress">
      <span className="price-track" aria-hidden="true">
        <i className={value >= 0 ? "is-up" : "is-down"} style={value >= 0 ? { left: "50%", width: `${width}%` } : { right: "50%", width: `${width}%` }} />
      </span>
      <b className={`num ${value >= 0 ? "tone-pos" : "tone-neg"}`}>{value > 0 ? "+" : ""}{value.toFixed(1)}%</b>
      {trend ? (
        <span className={`price-trend ${trend > 0 ? "tone-pos" : "tone-neg"}`} title={`${trend > 0 ? "Rising" : "Falling"} through the day`}>
          {trend > 0 ? <ArrowUp size={12} aria-label="rising" /> : <ArrowDown size={12} aria-label="falling" />}
        </span>
      ) : null}
    </span>
  );
}

export function PricesWorkspace() {
  const { dashboard, teamId } = useTeam();
  const prices = usePriceChanges();
  const now = useNow();
  const [filter, setFilter] = useState<Filter>("both");
  const [mine, setMine] = useState(false);
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(40);

  const owned = useMemo(() => new Set((dashboard?.data.team.picks ?? []).map((pick) => pick.player_id)), [dashboard]);
  const data = prices.data?.data;
  const rows = useMemo(() => {
    const text = query.trim().toLowerCase();
    return (data?.players ?? [])
      .map((player) => ({ player, status: nextStatus(player) }))
      .filter(({ player }) => !mine || owned.has(player.player_id))
      .filter(({ player }) => !text || player.name.toLowerCase().includes(text) || player.team.toLowerCase().includes(text))
      .filter(({ player }) => filter === "both" || (filter === "rise" ? (player.percent ?? 0) > 0 : (player.percent ?? 0) < 0))
      .sort((left, right) => Math.abs(right.player.percent ?? 0) - Math.abs(left.player.percent ?? 0));
  }, [data, filter, mine, owned, query]);

  const risers = (data?.players ?? []).filter((player) => isRise(nextStatus(player))).length;
  const fallers = (data?.players ?? []).filter((player) => isDrop(nextStatus(player))).length;
  const ownedAlerts = (data?.players ?? []).filter((player) => owned.has(player.player_id) && (isRise(nextStatus(player)) || isDrop(nextStatus(player))));
  const timer = countdown(data?.next_change_at, now);
  const at = data?.next_change_at ? new Date(data.next_change_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }) : null;

  return (
    <div className="stack prices-page">
      <PageLinkTabs parent="players" label="Explore" />
      <header className="page-head">
        <div>
          <span className="eyebrow">Explore · Prices</span>
          <h1>Price changes</h1>
          <p className="page-lede">Who is about to rise or drop in price tonight, from FPL&apos;s own figures.</p>
        </div>
        <div className="page-head-actions"><SourceBadge kind={prices.data?.meta.stale ? "cached" : "official"} /></div>
      </header>

      {prices.error && !data ? <DataState tone="error" title="Price changes are unavailable" action={<button className="btn btn-sm" onClick={prices.reload}>Try again</button>}>{prices.error}</DataState> : null}

      <Card className="price-clock" icon={<TrendingUp size={16} />} title="Next price changes" source="official">
        {prices.loading && !data ? <Skeleton lines={2} /> : (
          <div className="price-clock-body">
            <div>
              <strong className="price-countdown num">{timer ?? "—"}</strong>
              <small className="muted">{at ? `At ${at} your time` : "No change window announced"}</small>
            </div>
            <div className="price-counts">
              <span><b className="tone-pos">{risers}</b> likely to rise</span>
              <span><b className="tone-neg">{fallers}</b> likely to drop</span>
            </div>
          </div>
        )}
        {ownedAlerts.length ? (
          <p className="price-alert">
            <b>Your squad:</b>{" "}
            {ownedAlerts.map((player, index) => (
              <span key={player.player_id}>{index ? ", " : ""}{player.name} {isRise(nextStatus(player)) ? "likely to rise" : "likely to drop"}</span>
            ))}
            .
          </p>
        ) : null}
      </Card>

      {teamId && dashboard ? <PriceSwapsCard teamId={teamId} /> : null}

      <div className="toolbar" role="group" aria-label="Price change filters">
        <label className="search"><Search size={16} aria-hidden="true" /><span className="sr-only">Search players or clubs</span><input className="input" value={query} onChange={(event) => { setQuery(event.target.value); setLimit(40); }} placeholder="Search player or club" /></label>
        <Segmented<Filter> label="Direction" size="sm" value={filter} onChange={(value) => { setFilter(value); setLimit(40); }} options={[{ value: "both", label: "Rise & drop" }, { value: "rise", label: "Rises" }, { value: "drop", label: "Drops" }]} />
        {owned.size ? (
          <label className="check">
            <input type="checkbox" checked={mine} onChange={(event) => setMine(event.target.checked)} />
            <span>My team</span>
          </label>
        ) : null}
      </div>

      <Card className="price-card" source="official">
        {prices.loading && !data ? <Skeleton lines={10} /> : !rows.length ? (
          <DataState tone="empty" compact title="No players match">{mine ? "None of your players match these filters." : "Clear the search or change the filter."}</DataState>
        ) : (
          <>
            <ul className="price-list" aria-label="Players by price change progress">
              <li className="price-row price-head" aria-hidden="true">
                <span>Player</span><span>Tonight</span><span>Progress</span><span>Next</span>
              </li>
              {rows.slice(0, limit).map(({ player, status }) => {
                const next = player.projections.find((item) => item.offset === 1);
                const nextLabel = next ? statusFromLikelihood(next.likelihood) : null;
                return (
                  <li key={player.player_id} className={`price-row${owned.has(player.player_id) ? " is-owned" : ""}`}>
                    <PlayerChip name={player.name} team={player.team} teamShort={player.team_short} position={normalizePosition(player.position)} size={28}
                      meta={<><span>{player.position} · {player.team_short} · {price(player.price)}</span>{owned.has(player.player_id) ? <span className="tone-accent"> · Owned</span> : null}</>} />
                    <StatusPill status={status} />
                    <ProgressBar player={player} />
                    <span className="price-next" title="FPL's projection for the following change window">
                      {nextLabel && nextLabel !== "unlikely" ? <span className={isRise(nextLabel) ? "tone-pos" : "tone-neg"}>{isRise(nextLabel) ? "Rise" : "Drop"}</span> : <span className="faint">—</span>}
                    </span>
                  </li>
                );
              })}
            </ul>
            {rows.length > limit ? <div className="load-more"><button type="button" className="btn btn-sm" onClick={() => setLimit((value) => value + 40)}>Show more ({rows.length - limit} left)</button></div> : null}
          </>
        )}
      </Card>

      <details className="card-more">
        <summary>How do price changes work?</summary>
        <p className="card-note">
        Progress is FPL&apos;s published figure: at +100% a rise is due, at −100% a drop. FPL changes prices once a day and a player who has just changed is locked for a while.
        When you sell, FPL gives you only half of any rise since you bought (rounded down to £0.1m), so chase points first and use this for timing.
        </p>
      </details>
    </div>
  );
}
