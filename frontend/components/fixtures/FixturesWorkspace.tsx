"use client";

import { CalendarRange } from "lucide-react";
import { useMemo, useState } from "react";

import { useTeam } from "@/app/providers/TeamProvider";
import { FixtureCell } from "@/components/fixtures/FixtureCell";
import { Kit } from "@/components/kit/Kit";
import { DataState } from "@/components/states/DataState";
import { Card, Segmented, SourceBadge, Skeleton } from "@/components/ui/primitives";
import { fixed } from "@/lib/format";
import { cleanSheetLevel, runCleanSheets, runScore } from "@/lib/fpl/fixtures";
import { useFixtureMatrix } from "@/lib/hooks/data";

type Horizon = "3" | "5" | "8";
type Order = "easiest" | "hardest" | "name";
type View = "difficulty" | "cleanSheet";

/** Every club's upcoming run with explicit home/away, blanks and doubles. Clubs you own are highlighted. */
export function FixturesWorkspace() {
  const { dashboard } = useTeam();
  const [horizon, setHorizon] = useState<Horizon>("5");
  const [order, setOrder] = useState<Order>("easiest");
  const [ownedOnly, setOwnedOnly] = useState(false);
  const [view, setView] = useState<View>("difficulty");
  const matrix = useFixtureMatrix(Number(horizon));

  const owned = useMemo(() => {
    const counts = new Map<string, number>();
    for (const pick of dashboard?.data.team.picks ?? []) {
      const short = pick.team_short ?? "";
      if (short) counts.set(short, (counts.get(short) ?? 0) + 1);
    }
    return counts;
  }, [dashboard]);

  const gameweeks = matrix.data?.data.gameweeks ?? [];
  const rows = useMemo(() => {
    const teams = matrix.data?.data.teams ?? [];
    const scored = teams
      .filter((team) => !ownedOnly || owned.has(team.team_short))
      .map((team) => ({
        team,
        score: runScore(team),
        cleanSheets: runCleanSheets(team),
        blanks: team.fixtures.filter((cell) => cell.fixture_count === 0).length,
        doubles: team.fixtures.filter((cell) => cell.fixture_count > 1).length,
      }));
    if (order === "name") return scored.sort((left, right) => left.team.team.localeCompare(right.team.team));
    // Easiest means the lowest difficulty score, or the most expected clean sheets.
    const ease = (row: (typeof scored)[number]) => (view === "cleanSheet" ? -(row.cleanSheets ?? 0) : row.score);
    return scored.sort((left, right) => (order === "easiest" ? ease(left) - ease(right) : ease(right) - ease(left)));
  }, [matrix.data, order, ownedOnly, owned, view]);
  const hasCleanSheets = rows.some((row) => row.cleanSheets != null);
  const showCleanSheets = view === "cleanSheet" && hasCleanSheets;

  const columns = `minmax(148px, 1.4fr) repeat(${gameweeks.length}, minmax(58px, 1fr)) minmax(64px, 0.7fr)`;

  return (
    <div className="stack">
      <header className="page-head">
        <div>
          <span className="eyebrow">Fixture planner</span>
          <h1>Fixtures</h1>
          <p className="page-lede">Every club&apos;s next run, with home and away spelled out. Lower run scores are easier; blanks count against a club and doubles count for it. Clean sheet % shows each club&apos;s chance of keeping one.</p>
        </div>
      </header>

      <div className="toolbar" role="group" aria-label="Fixture options">
        <Segmented<Horizon> label="Horizon" value={horizon} onChange={setHorizon} options={[{ value: "3", label: "3 GWs" }, { value: "5", label: "5 GWs" }, { value: "8", label: "8 GWs" }]} />
        {hasCleanSheets ? <Segmented<View> label="Show" value={view} onChange={setView} options={[{ value: "difficulty", label: "Difficulty" }, { value: "cleanSheet", label: "Clean sheet %" }]} /> : null}
        <Segmented<Order> label="Sort clubs" value={order} onChange={setOrder} options={[{ value: "easiest", label: "Easiest" }, { value: "hardest", label: "Hardest" }, { value: "name", label: "A–Z" }]} />
        {owned.size ? (
          <label className="check">
            <input type="checkbox" checked={ownedOnly} onChange={(event) => setOwnedOnly(event.target.checked)} />
            <span>Only my clubs</span>
          </label>
        ) : null}
      </div>

      {showCleanSheets ? (
        <div className="legend" aria-label="Clean sheet legend">
          <span>Clean sheet chance</span>
          {[0.45, 0.35, 0.25, 0.15, 0.08].map((chance, index) => <span key={chance} className={`fx fx-key fx-key-wide fdr-${cleanSheetLevel(chance)}`}>{["40%+", "30%", "20%", "12%", "<12%"][index]}</span>)}
          <span className="legend-note">From official xG for and against, adjusted for home and away. <SourceBadge kind="derived" pinned /></span>
        </div>
      ) : (
        <div className="legend" aria-label="Difficulty legend">
          <span>Difficulty</span>
          {[1, 2, 3, 4, 5].map((level) => <span key={level} className={`fx fx-key fdr-${level}`}>{level}</span>)}
          <span className="legend-note"><b>H</b> home · <b>A</b> away · <b>DGW</b> double · <b>Blank</b> no match</span>
        </div>
      )}

      {matrix.data?.meta.stale ? <DataState tone="stale" compact title="Showing cached fixtures">The official fixture feed did not respond; fixtures can move after this snapshot.</DataState> : null}

      <Card title="Fixture runs" eyebrow={gameweeks.length ? `GW${gameweeks[0]}–${gameweeks[gameweeks.length - 1]}` : undefined} icon={<CalendarRange size={16} />} source={matrix.data?.meta.stale ? "cached" : "official"} className="fixtures-card">
        {matrix.loading && !matrix.data ? <Skeleton lines={12} /> : matrix.error && !matrix.data ? (
          <DataState tone="error" title="Fixtures could not be loaded" action={<button className="btn btn-sm" onClick={matrix.reload}>Try again</button>}>{matrix.error}</DataState>
        ) : !rows.length ? (
          <DataState tone="empty" compact title="No fixtures to show">{ownedOnly ? "None of your clubs have fixtures in this window." : "The official feed returned no fixtures for this window."}</DataState>
        ) : (
          <div className="table-scroll">
            <div className="fx-table fx-table-full" role="table" aria-label={`Fixture runs for the next ${gameweeks.length} Gameweeks`}>
              <div className="fx-tr fx-thead" role="row" style={{ gridTemplateColumns: columns }}>
                <span role="columnheader">Club</span>
                {gameweeks.map((gameweek) => <span role="columnheader" key={gameweek}>GW{gameweek}</span>)}
                {showCleanSheets
                  ? <span role="columnheader" className="num" title="Expected clean sheets over the run: the sum of each fixture's chance">xCS <SourceBadge kind="derived" /></span>
                  : <span role="columnheader" className="num" title="Sum of difficulty; blanks count 6, doubles reduce the score">Run <SourceBadge kind="derived" /></span>}
              </div>
              {rows.map(({ team, score, cleanSheets, blanks, doubles }) => {
                const count = owned.get(team.team_short);
                return (
                  <div className={`fx-tr${count ? " is-owned" : ""}`} role="row" key={team.team_id} style={{ gridTemplateColumns: columns }}>
                    <span role="rowheader" className="fx-club">
                      <Kit team={team.team} teamShort={team.team_short} size={26} bare />
                      <span>
                        <b>{team.team}</b>
                        <small>{count ? `${count} owned` : team.team_short}{doubles ? ` · ${doubles} double` : ""}{blanks ? ` · ${blanks} blank` : ""}</small>
                      </span>
                    </span>
                    {gameweeks.map((gameweek) => (
                      <span role="cell" key={gameweek}><FixtureCell cell={team.fixtures.find((cell) => cell.event === gameweek)} metric={showCleanSheets ? "cleanSheet" : "difficulty"} /></span>
                    ))}
                    <span role="cell" className="num fx-score">{showCleanSheets ? fixed(cleanSheets, 1) : fixed(score, 1)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
