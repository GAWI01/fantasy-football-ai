import type { FixtureMatrixCell } from "@/lib/contracts";
import { cellCleanSheets, cellOpponents, cleanSheetLevel, fdrLevel } from "@/lib/fpl/fixtures";

/**
 * One Gameweek cell: opponent(s), explicit H/A and difficulty colour. Blanks and
 * doubles are called out. With `metric="cleanSheet"` the colour and a figure
 * show the club's chance of a clean sheet instead of the official difficulty.
 */
export function FixtureCell({ cell, compact = false, metric = "difficulty" }: { cell: FixtureMatrixCell | undefined; compact?: boolean; metric?: "difficulty" | "cleanSheet" }) {
  if (!cell || cell.fixture_count === 0) {
    return <span className="fx fx-blank" title="Blank Gameweek: no fixture"><b>Blank</b></span>;
  }
  const opponents = cellOpponents(cell);
  const cleanSheets = metric === "cleanSheet" ? cellCleanSheets(cell) : null;
  // A double's two chances are averaged for the colour; the figure is per match.
  const perMatch = cleanSheets == null ? null : cleanSheets / cell.fixture_count;
  const level = metric === "cleanSheet" ? cleanSheetLevel(perMatch) : fdrLevel(cell.difficulty);
  const measure = metric === "cleanSheet"
    ? `clean sheet chance ${perMatch == null ? "unknown" : `${Math.round(perMatch * 100)}%`}${cell.fixture_count > 1 ? " per match" : ""}`
    : `difficulty ${cell.difficulty ?? "unknown"}`;
  const title = `GW${cell.event}: ${opponents.map((opponent) => `${opponent.short} ${opponent.home ? "home" : opponent.home === false ? "away" : ""}`.trim()).join(" and ")} · ${measure}${cell.fixture_count > 1 ? " · double Gameweek" : ""}`;
  return (
    <span className={`fx fdr-${level}${cell.fixture_count > 1 ? " fx-double" : ""}`} title={title}>
      {opponents.map((opponent, index) => (
        <span key={`${opponent.short}-${index}`} className="fx-opp" aria-hidden="true">
          <b>{opponent.short}</b>
          {opponent.home != null ? <small className={opponent.home ? "fx-h" : "fx-a"}>{opponent.home ? "H" : "A"}</small> : null}
        </span>
      ))}
      {perMatch != null ? <em className="fx-cs" aria-hidden="true">{Math.round(perMatch * 100)}%</em> : null}
      {cell.fixture_count > 1 && !compact ? <em className="fx-dgw" aria-hidden="true">DGW</em> : null}
      <span className="sr-only">{title}</span>
    </span>
  );
}
