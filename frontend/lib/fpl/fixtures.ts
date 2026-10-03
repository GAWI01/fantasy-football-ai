import type { FixtureMatrixCell, FixtureMatrixTeam } from "@/lib/contracts";

export type Opponent = { short: string; home: boolean | null };

/** The fixture matrix encodes opponents as "CHE (H)" / "ARS (A)". */
export function parseOpponent(value: string): Opponent {
  const match = value.match(/^(.*?)\s*\((H|A)\)\s*$/i);
  if (!match) return { short: value.trim(), home: null };
  return { short: match[1].trim(), home: match[2].toUpperCase() === "H" };
}

export function cellOpponents(cell: FixtureMatrixCell): Opponent[] {
  return cell.opponents.map(parseOpponent);
}

export function opponentLabel(opponent: Opponent, style: "short" | "case" = "case"): string {
  if (opponent.home == null) return opponent.short;
  if (style === "case") return opponent.home ? opponent.short.toUpperCase() : opponent.short.toLowerCase();
  return `${opponent.short} (${opponent.home ? "H" : "A"})`;
}

/**
 * Lower is easier. Blank Gameweeks score as 6 (worse than any fixture) and
 * doubles are rewarded, so a run's total reflects real FPL opportunity.
 */
export function runScore(team: FixtureMatrixTeam, events?: number[]): number {
  const cells = events ? team.fixtures.filter((cell) => events.includes(cell.event)) : team.fixtures;
  return cells.reduce((total, cell) => {
    if (!cell.fixture_count) return total + 6;
    const difficulty = cell.difficulty ?? 3;
    return total + difficulty - (cell.fixture_count - 1) * 2.5;
  }, 0);
}

export function fdrLevel(difficulty: number | null | undefined): number {
  return typeof difficulty === "number" ? Math.max(1, Math.min(5, Math.round(difficulty))) : 0;
}
