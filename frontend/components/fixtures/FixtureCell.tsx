import type { FixtureMatrixCell } from "@/lib/contracts";
import { cellOpponents, fdrLevel } from "@/lib/fpl/fixtures";

/** One Gameweek cell: opponent(s), explicit H/A and difficulty colour. Blanks and doubles are called out. */
export function FixtureCell({ cell, compact = false }: { cell: FixtureMatrixCell | undefined; compact?: boolean }) {
  if (!cell || cell.fixture_count === 0) {
    return <span className="fx fx-blank" title="Blank Gameweek: no fixture"><b>Blank</b></span>;
  }
  const opponents = cellOpponents(cell);
  const level = fdrLevel(cell.difficulty);
  const title = `GW${cell.event}: ${opponents.map((opponent) => `${opponent.short} ${opponent.home ? "home" : opponent.home === false ? "away" : ""}`.trim()).join(" and ")} · difficulty ${cell.difficulty ?? "unknown"}${cell.fixture_count > 1 ? " · double Gameweek" : ""}`;
  return (
    <span className={`fx fdr-${level}${cell.fixture_count > 1 ? " fx-double" : ""}`} title={title}>
      {opponents.map((opponent, index) => (
        <span key={`${opponent.short}-${index}`} className="fx-opp" aria-hidden="true">
          <b>{opponent.short}</b>
          {opponent.home != null ? <small className={opponent.home ? "fx-h" : "fx-a"}>{opponent.home ? "H" : "A"}</small> : null}
        </span>
      ))}
      {cell.fixture_count > 1 && !compact ? <em className="fx-dgw" aria-hidden="true">DGW</em> : null}
      <span className="sr-only">{title}</span>
    </span>
  );
}
