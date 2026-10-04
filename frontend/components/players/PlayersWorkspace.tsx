"use client";

import { ArrowDown, ArrowUp, Plus, Scale, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useTeam } from "@/app/providers/TeamProvider";
import { FixtureCell } from "@/components/fixtures/FixtureCell";
import { Kit } from "@/components/kit/Kit";
import { PlayerChip } from "@/components/player/PlayerChip";
import { DataState } from "@/components/states/DataState";
import { Sheet } from "@/components/ui/Sheet";
import { Card, Segmented, Skeleton, SourceBadge } from "@/components/ui/primitives";
import type { FixtureMatrixTeam, PlayerSummary } from "@/lib/contracts";
import { fixed, percent, price } from "@/lib/format";
import { availabilityFromStatus, normalizePosition, type Position } from "@/lib/fpl/rules";
import { useFixtureMatrix, usePlayerMarket } from "@/lib/hooks/data";

type PositionFilter = "ALL" | Position;
type SortKey = "xp" | "value" | "form" | "price" | "ownership" | "event" | "xgi";

const SORTS: Array<{ key: SortKey; label: string; get: (player: PlayerSummary) => number | null }> = [
  { key: "xp", label: "xP", get: (player) => player.predicted_points ?? null },
  { key: "value", label: "xP/£", get: (player) => (player.predicted_points != null && player.price ? player.predicted_points / player.price : null) },
  { key: "form", label: "Form", get: (player) => player.form ?? null },
  { key: "event", label: "GW pts", get: (player) => player.event_points ?? null },
  { key: "xgi", label: "xGI", get: (player) => player.expected_goal_involvements ?? null },
  { key: "price", label: "Price", get: (player) => player.price ?? null },
  { key: "ownership", label: "Own%", get: (player) => player.ownership ?? null },
];

export type PlayersSearch = { position?: string; q?: string; compare?: string; sort?: string };

function readUrl(search: PlayersSearch) {
  const params = new URLSearchParams(Object.entries(search).filter((entry): entry is [string, string] => typeof entry[1] === "string"));
  const position: PositionFilter = normalizePosition(params.get("position")) ?? "ALL";
  const sort = SORTS.some((item) => item.key === params.get("sort")) ? params.get("sort") as SortKey : "xp";
  const compare = (params.get("compare") ?? "").split(",").map(Number).filter((value, index, all) => Number.isInteger(value) && value > 0 && all.indexOf(value) === index).slice(0, 4);
  return { position, query: params.get("q") ?? "", compare, sort };
}

function MarketPlayerDetail({ player, team, owned }: { player: PlayerSummary; team: FixtureMatrixTeam | undefined; owned: boolean }) {
  const availability = availabilityFromStatus(player.status, player.chance_of_playing_next_round);
  return (
    <div className="pdetail">
      <div className="pdetail-hero">
        <Kit team={player.team} teamShort={player.team_short} goalkeeper={normalizePosition(player.position) === "GKP"} size={64} />
        <div>
          <span className="eyebrow">{player.position} · {player.team}</span>
          <div className="row row-wrap pdetail-tags">
            <span className={`pill ${availability.tone === "ok" ? "pill-pos" : availability.tone === "warn" ? "pill-warn" : availability.tone === "risk" ? "pill-neg" : ""}`}><i className={`dot dot-${availability.tone}`} />{availability.label}</span>
            {owned ? <span className="pill pill-accent">In your squad</span> : null}
          </div>
        </div>
      </div>
      <div className="facts">
        <div className="fact"><span className="fact-label">Next GW <SourceBadge kind="model" /></span><strong className="fact-value tone-accent">{fixed(player.predicted_points)} xP</strong></div>
        <div className="fact"><span className="fact-label">Exp. minutes <SourceBadge kind="model" /></span><strong className="fact-value">{player.xmins == null ? "—" : Math.round(player.xmins)}</strong></div>
        <div className="fact"><span className="fact-label">Start chance <SourceBadge kind="model" /></span><strong className="fact-value">{percent(player.start_probability, { fraction: true })}</strong></div>
        <div className="fact"><span className="fact-label">Price <SourceBadge kind="official" /></span><strong className="fact-value">{price(player.price)}</strong></div>
        <div className="fact"><span className="fact-label">Form <SourceBadge kind="official" /></span><strong className="fact-value">{fixed(player.form)}</strong></div>
        <div className="fact"><span className="fact-label">Owned by <SourceBadge kind="official" /></span><strong className="fact-value">{percent(player.ownership, { digits: 1 })}</strong></div>
      </div>
      <section className="pdetail-section">
        <h3>Upcoming fixtures <SourceBadge kind="official" /></h3>
        {team ? <div className="fx-strip">{team.fixtures.map((cell) => <div key={cell.event}><small>GW{cell.event}</small><FixtureCell cell={cell} /></div>)}</div> : <p className="faint">Fixture run unavailable.</p>}
      </section>
      <section className="pdetail-section">
        <h3>This Gameweek <SourceBadge kind="official" /></h3>
        <dl className="season-grid">
          <div><dt>Points</dt><dd>{player.event_points ?? "—"}</dd></div>
          <div><dt>Minutes</dt><dd>{player.minutes ?? "—"}</dd></div>
          <div><dt>Goals</dt><dd>{player.goals ?? "—"}</dd></div>
          <div><dt>Assists</dt><dd>{player.assists ?? "—"}</dd></div>
          <div><dt>Bonus</dt><dd>{player.bonus ?? "—"}</dd></div>
          <div><dt>BPS</dt><dd>{player.bps ?? "—"}</dd></div>
        </dl>
      </section>
      <section className="pdetail-section">
        <h3>Season underlying <SourceBadge kind="official" /></h3>
        <dl className="season-grid">
          <div><dt>xG</dt><dd>{fixed(player.expected_goals, 2)}</dd></div>
          <div><dt>xA</dt><dd>{fixed(player.expected_assists, 2)}</dd></div>
          <div><dt>xGI</dt><dd>{fixed(player.expected_goal_involvements, 2)}</dd></div>
          <div><dt>ICT</dt><dd>{fixed(player.ict_index)}</dd></div>
        </dl>
      </section>
      {player.news ? <section className="pdetail-section pdetail-news"><div><h3>Official news</h3><p>{player.news}</p></div></section> : null}
    </div>
  );
}

const COMPARE_ROWS: Array<{ label: string; get: (player: PlayerSummary) => number | null; format: (value: number | null) => string; higher?: boolean; source: "model" | "official" | "derived" }> = [
  { label: "Next GW xP", get: (player) => player.predicted_points ?? null, format: (value) => fixed(value), higher: true, source: "model" },
  { label: "xMins", get: (player) => player.xmins ?? null, format: (value) => (value == null ? "—" : String(Math.round(value))), higher: true, source: "model" },
  { label: "xP per £m", get: (player) => (player.predicted_points != null && player.price ? player.predicted_points / player.price : null), format: (value) => fixed(value, 2), higher: true, source: "derived" },
  { label: "Price", get: (player) => player.price ?? null, format: (value) => price(value), higher: false, source: "official" },
  { label: "Form", get: (player) => player.form ?? null, format: (value) => fixed(value), higher: true, source: "official" },
  { label: "Season xGI", get: (player) => player.expected_goal_involvements ?? null, format: (value) => fixed(value, 2), higher: true, source: "official" },
  { label: "Ownership", get: (player) => player.ownership ?? null, format: (value) => percent(value, { digits: 1 }), source: "official" },
];

export function PlayersWorkspace({ search = {} }: { search?: PlayersSearch }) {
  const { dashboard } = useTeam();
  const market = usePlayerMarket();
  const matrix = useFixtureMatrix(5);
  const [initial] = useState(() => readUrl(search));
  const [position, setPosition] = useState<PositionFilter>(initial.position);
  const [query, setQuery] = useState(initial.query);
  const [sort, setSort] = useState<SortKey>(initial.sort);
  const [ascending, setAscending] = useState(false);
  const [maxPrice, setMaxPrice] = useState<number | null>(null);
  const [compare, setCompare] = useState<number[]>(initial.compare);
  const [detail, setDetail] = useState<number | null>(null);
  const [compareOpen, setCompareOpen] = useState(false);
  const [limit, setLimit] = useState(60);

  const players = useMemo(() => market.data?.data.players ?? dashboard?.data.players?.players ?? [], [market.data, dashboard]);
  const ownedIds = useMemo(() => new Set((dashboard?.data.team.picks ?? []).map((pick) => pick.player_id)), [dashboard]);
  const teamByShort = useMemo(() => new Map((matrix.data?.data.teams ?? []).map((team) => [team.team_short, team])), [matrix.data]);
  const byId = useMemo(() => new Map(players.map((player) => [player.player_id, player])), [players]);
  const priceCap = useMemo(() => Math.max(4, ...players.map((player) => player.price ?? 0)), [players]);

  const visible = useMemo(() => {
    const getter = SORTS.find((item) => item.key === sort)?.get ?? SORTS[0].get;
    const text = query.trim().toLowerCase();
    return players
      .filter((player) => position === "ALL" || normalizePosition(player.position) === position)
      .filter((player) => !text || player.name.toLowerCase().includes(text) || player.team.toLowerCase().includes(text) || player.team_short.toLowerCase() === text)
      .filter((player) => maxPrice == null || (player.price ?? 0) <= maxPrice)
      .sort((left, right) => {
        const a = getter(left);
        const b = getter(right);
        if (a == null && b == null) return 0;
        if (a == null) return 1;
        if (b == null) return -1;
        return ascending ? a - b : b - a;
      });
  }, [players, position, query, sort, ascending, maxPrice]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const set = (key: string, value: string | null) => (value ? params.set(key, value) : params.delete(key));
    set("position", position === "ALL" ? null : position);
    set("q", query || null);
    set("sort", sort === "xp" ? null : sort);
    set("compare", compare.length ? compare.join(",") : null);
    window.history.replaceState(window.history.state, "", `${window.location.pathname}${params.size ? `?${params}` : ""}${window.location.hash}`);
  }, [position, query, sort, compare]);

  const toggleCompare = (id: number) => setCompare((current) => current.includes(id) ? current.filter((value) => value !== id) : current.length < 4 ? [...current, id] : current);
  const compared = compare.map((id) => byId.get(id)).filter((player): player is PlayerSummary => Boolean(player));
  const detailPlayer = detail != null ? byId.get(detail) ?? null : null;
  const live = market.data?.data.status === "LIVE" && market.data.data.finished !== true;
  const marketSource = market.data?.meta.stale ? "cached" : live ? "live" : "official";

  function header(key: SortKey, label: string) {
    const active = sort === key;
    return (
      <th scope="col" className="num" aria-sort={active ? (ascending ? "ascending" : "descending") : undefined}>
        <button type="button" className="sort-btn" onClick={() => { if (active) setAscending((value) => !value); else { setSort(key); setAscending(key === "price"); } }}>
          {label}{active ? (ascending ? <ArrowUp size={12} aria-hidden="true" /> : <ArrowDown size={12} aria-hidden="true" />) : null}
        </button>
      </th>
    );
  }

  return (
    <div className="players-page">
      <header className="page-head">
        <div>
          <span className="eyebrow">Player market{market.data?.data.current_event ? ` · GW${market.data.data.current_event}` : ""}</span>
          <h1>Players</h1>
          <p>Every player with official stats and the model’s next-Gameweek projection. Shortlist up to four to compare.</p>
        </div>
        <div className="page-head-actions"><SourceBadge kind={marketSource} /><SourceBadge kind="model" /></div>
      </header>

      {market.error && !players.length ? <DataState tone="error" title="The player market is unavailable" action={<button className="btn btn-sm" onClick={market.reload}>Try again</button>}>{market.error}</DataState> : null}
      {market.data?.data.model_validation_state === "unverified" ? <DataState tone="warning" compact title="Unverified model forecasts">The forecasts are shown for evaluation only.</DataState> : null}
      {market.data?.errors.some((item) => item.area === "model") ? <DataState tone="warning" compact title="Model projections unavailable">Official data is shown; xP and xMins columns are empty until projections load.</DataState> : null}
      {market.data?.meta.stale ? <DataState tone="stale" compact title="Showing cached FPL data">The official service did not respond.</DataState> : null}

      <div className="toolbar">
        <label className="search"><Search size={16} aria-hidden="true" /><span className="sr-only">Search players or clubs</span><input className="input" value={query} onChange={(event) => { setQuery(event.target.value); setLimit(60); }} placeholder="Search player or club" /></label>
        <Segmented<PositionFilter> label="Position" size="sm" value={position} onChange={(value) => { setPosition(value); setLimit(60); }} options={[{ value: "ALL", label: "All" }, { value: "GKP", label: "GK" }, { value: "DEF", label: "DEF" }, { value: "MID", label: "MID" }, { value: "FWD", label: "FWD" }]} />
        <label className="price-filter">
          <span>Max {maxPrice == null ? "price" : price(maxPrice)}</span>
          <input type="range" min={4} max={Math.ceil(priceCap * 2) / 2} step={0.5} value={maxPrice ?? Math.ceil(priceCap * 2) / 2} onChange={(event) => { const value = Number(event.target.value); setMaxPrice(value >= priceCap ? null : value); }} aria-label="Maximum price in millions" />
        </label>
        <label className="sort-mobile">
          <span className="sr-only">Sort by</span>
          <select className="select" value={sort} onChange={(event) => { setSort(event.target.value as SortKey); setAscending(event.target.value === "price"); }}>
            {SORTS.map((item) => <option key={item.key} value={item.key}>Sort: {item.label}</option>)}
          </select>
        </label>
      </div>

      {compared.length ? (
        <div className="compare-tray" role="region" aria-label="Shortlist">
          <Scale size={16} aria-hidden="true" />
          <div className="compare-chips">{compared.map((player) => <button type="button" key={player.player_id} className="pill" onClick={() => toggleCompare(player.player_id)} aria-label={`Remove ${player.name} from shortlist`}>{player.name}<X size={12} aria-hidden="true" /></button>)}</div>
          <button type="button" className="btn btn-sm btn-primary" disabled={compared.length < 2} onClick={() => setCompareOpen(true)}>Compare {compared.length}</button>
        </div>
      ) : null}

      <Card className="market-card">
        {market.loading && !players.length ? <Skeleton lines={10} /> : (
          <>
            <div className="table-wrap market-table">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Player</th>
                    <th scope="col">Next 3</th>
                    {header("xp", "xP")}
                    <th scope="col" className="num">xMins</th>
                    {header("value", "xP/£")}
                    {header("form", "Form")}
                    {header("event", "GW pts")}
                    {header("price", "Price")}
                    {header("ownership", "Own%")}
                    <th scope="col"><span className="sr-only">Shortlist</span></th>
                  </tr>
                </thead>
                <tbody>
                  {visible.slice(0, limit).map((player) => {
                    const owned = ownedIds.has(player.player_id);
                    const chosen = compare.includes(player.player_id);
                    const availability = availabilityFromStatus(player.status, player.chance_of_playing_next_round);
                    const team = teamByShort.get(player.team_short);
                    return (
                      <tr key={player.player_id} className={owned ? "is-owned" : undefined}>
                        <td>
                          <button type="button" className="row-link" onClick={() => setDetail(player.player_id)} aria-label={`Open ${player.name} details`}>
                            <PlayerChip name={player.name} team={player.team} teamShort={player.team_short} position={normalizePosition(player.position)} size={28} meta={<><span>{player.position} · {player.team_short}</span>{availability.tone !== "ok" ? <span className={`tone-${availability.tone === "risk" ? "neg" : "warn"}`}> · {availability.label}</span> : null}{owned ? <span className="tone-accent"> · Owned</span> : null}</>} />
                          </button>
                        </td>
                        <td><span className="fx-mini">{team ? team.fixtures.slice(0, 3).map((cell) => <FixtureCell key={cell.event} cell={cell} compact />) : <span className="faint">—</span>}</span></td>
                        <td className="num"><b className="tone-accent">{fixed(player.predicted_points)}</b></td>
                        <td className="num">{player.xmins == null ? "—" : Math.round(player.xmins)}</td>
                        <td className="num">{player.predicted_points != null && player.price ? fixed(player.predicted_points / player.price, 2) : "—"}</td>
                        <td className="num">{fixed(player.form)}</td>
                        <td className="num">{player.event_points ?? "—"}</td>
                        <td className="num">{price(player.price)}</td>
                        <td className="num">{percent(player.ownership, { digits: 1 })}</td>
                        <td>
                          <button type="button" className={`icon-btn icon-btn-sm${chosen ? " is-on" : ""}`} aria-pressed={chosen} aria-label={`${chosen ? "Remove" : "Add"} ${player.name} ${chosen ? "from" : "to"} shortlist`} disabled={!chosen && compare.length >= 4} onClick={() => toggleCompare(player.player_id)}>
                            {chosen ? <X size={14} aria-hidden="true" /> : <Plus size={14} aria-hidden="true" />}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {!visible.length ? <DataState tone="empty" compact title="No players match">Clear the search or widen the filters.</DataState> : null}
            {visible.length > limit ? <div className="load-more"><button type="button" className="btn btn-sm" onClick={() => setLimit((value) => value + 60)}>Show more ({visible.length - limit} left)</button></div> : null}
          </>
        )}
      </Card>

      <Sheet open={detailPlayer != null} onClose={() => setDetail(null)} title={detailPlayer?.name ?? ""} subtitle={detailPlayer ? `${detailPlayer.position} · ${detailPlayer.team_short} · ${price(detailPlayer.price)}` : undefined}
        footer={detailPlayer ? <button type="button" className="btn btn-sm" disabled={!compare.includes(detailPlayer.player_id) && compare.length >= 4} onClick={() => toggleCompare(detailPlayer.player_id)}>{compare.includes(detailPlayer.player_id) ? "Remove from shortlist" : "Add to shortlist"}</button> : undefined}>
        {detailPlayer ? <MarketPlayerDetail player={detailPlayer} team={teamByShort.get(detailPlayer.team_short)} owned={ownedIds.has(detailPlayer.player_id)} /> : null}
      </Sheet>

      <Sheet open={compareOpen && compared.length >= 2} onClose={() => setCompareOpen(false)} title="Compare players" subtitle="Best value per row is highlighted" size="lg">
        <div className="compare-grid" style={{ gridTemplateColumns: `minmax(96px, 0.9fr) repeat(${compared.length}, minmax(0, 1fr))` }}>
          <span />
          {compared.map((player) => (
            <div key={player.player_id} className="compare-col-head">
              <Kit team={player.team} teamShort={player.team_short} goalkeeper={normalizePosition(player.position) === "GKP"} size={40} />
              <strong>{player.name}</strong>
              <small>{player.position} · {player.team_short}</small>
            </div>
          ))}
          {COMPARE_ROWS.map((row) => {
            const values = compared.map(row.get);
            const numeric = values.filter((value): value is number => value != null);
            const best = row.higher == null || !numeric.length ? null : row.higher ? Math.max(...numeric) : Math.min(...numeric);
            return [
              <span key={`${row.label}-label`} className="compare-label">{row.label}<SourceBadge kind={row.source} /></span>,
              ...values.map((value, index) => <span key={`${row.label}-${compared[index].player_id}`} className={`compare-val num${best != null && value === best && numeric.length > 1 ? " is-best" : ""}`}>{row.format(value)}</span>),
            ];
          })}
          <span className="compare-label">Next fixtures<SourceBadge kind="official" /></span>
          {compared.map((player) => <span key={`fx-${player.player_id}`} className="fx-mini fx-mini-col">{teamByShort.get(player.team_short)?.fixtures.slice(0, 3).map((cell) => <FixtureCell key={cell.event} cell={cell} compact />) ?? "—"}</span>)}
        </div>
      </Sheet>
    </div>
  );
}
