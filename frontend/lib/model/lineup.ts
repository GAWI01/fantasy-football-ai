import { formationLabel, validateStartingXI } from "@/lib/fpl/rules";
import type { SquadPlayer } from "@/lib/model/squad";

/** A local lineup simulation. Nothing here is ever sent to FPL. */
export type Lineup = {
  starters: number[];
  /** Bench order; index 0 is the substitute goalkeeper. */
  bench: number[];
  captain: number | null;
  vice: number | null;
};

export type LineupResult = { lineup: Lineup; ok: boolean; message: string };

export function officialLineup(squad: SquadPlayer[]): Lineup {
  const bench = squad.filter((player) => !player.isStarter).sort((left, right) => left.slot - right.slot);
  const goalkeeper = bench.find((player) => player.position === "GKP");
  const ordered = goalkeeper ? [goalkeeper, ...bench.filter((player) => player !== goalkeeper)] : bench;
  return {
    starters: squad.filter((player) => player.isStarter).sort((left, right) => left.slot - right.slot).map((player) => player.id),
    bench: ordered.map((player) => player.id),
    captain: squad.find((player) => player.isCaptain)?.id ?? null,
    vice: squad.find((player) => player.isVice)?.id ?? null,
  };
}

export function modelLineup(squad: SquadPlayer[], xi: SquadPlayer[], bench: SquadPlayer[], captain: SquadPlayer | null, vice: SquadPlayer | null): Lineup | null {
  if (xi.length !== 11 || bench.length !== 4) return null;
  const goalkeeper = bench.find((player) => player.position === "GKP");
  const ordered = goalkeeper ? [goalkeeper, ...bench.filter((player) => player !== goalkeeper)] : bench;
  const ids = new Set(squad.map((player) => player.id));
  if (![...xi, ...bench].every((player) => ids.has(player.id))) return null;
  return { starters: xi.map((player) => player.id), bench: ordered.map((player) => player.id), captain: captain?.id ?? null, vice: vice?.id ?? null };
}

function byId(squad: SquadPlayer[]) {
  return new Map(squad.map((player) => [player.id, player]));
}

function bestOther(starters: number[], exclude: Array<number | null>, squad: SquadPlayer[]): number | null {
  const map = byId(squad);
  return [...starters]
    .filter((id) => !exclude.includes(id))
    .sort((left, right) => (map.get(right)?.xp ?? -1) - (map.get(left)?.xp ?? -1))[0] ?? null;
}

/** Keeps the armbands on starters after a substitution. */
function repairArmbands(lineup: Lineup, squad: SquadPlayer[]): { lineup: Lineup; note: string | null } {
  let { captain, vice } = lineup;
  let note: string | null = null;
  const map = byId(squad);
  if (captain != null && !lineup.starters.includes(captain)) {
    const benched = map.get(captain)?.name ?? "Your captain";
    captain = vice != null && lineup.starters.includes(vice) ? vice : bestOther(lineup.starters, [], squad);
    vice = bestOther(lineup.starters, [captain], squad);
    note = `${benched} was benched, so the armband moved to ${map.get(captain ?? -1)?.name ?? "another starter"}.`;
  }
  if (vice != null && !lineup.starters.includes(vice)) {
    vice = bestOther(lineup.starters, [captain], squad);
    note = note ?? `Vice-captain moved to ${map.get(vice ?? -1)?.name ?? "another starter"}.`;
  }
  return { lineup: { ...lineup, captain, vice }, note };
}

export function swapPlayers(lineup: Lineup, firstId: number, secondId: number, squad: SquadPlayer[]): LineupResult {
  const map = byId(squad);
  const first = map.get(firstId);
  const second = map.get(secondId);
  if (!first || !second || firstId === secondId) return { lineup, ok: false, message: "Choose two different players." };
  const firstStarts = lineup.starters.includes(firstId);
  const secondStarts = lineup.starters.includes(secondId);

  if (!firstStarts && !secondStarts) {
    if ((first.position === "GKP") !== (second.position === "GKP")) {
      return { lineup, ok: false, message: "The substitute goalkeeper always sits first on the bench." };
    }
    const bench = lineup.bench.map((id) => (id === firstId ? secondId : id === secondId ? firstId : id));
    return { lineup: { ...lineup, bench }, ok: true, message: "Bench order updated." };
  }
  if (firstStarts && secondStarts) {
    return { lineup, ok: false, message: "Both players already start. Pick a bench player to swap with." };
  }
  const outId = firstStarts ? firstId : secondId;
  const inId = firstStarts ? secondId : firstId;
  const starters = lineup.starters.map((id) => (id === outId ? inId : id));
  const validation = validateStartingXI(starters.map((id) => ({ position: map.get(id)?.position ?? null })));
  if (!validation.valid) {
    return { lineup, ok: false, message: `That swap breaks the formation. ${validation.reason}` };
  }
  const bench = lineup.bench.map((id) => (id === inId ? outId : id));
  const repaired = repairArmbands({ ...lineup, starters, bench }, squad);
  const formation = formationLabel(starters.map((id) => ({ position: map.get(id)?.position ?? null })));
  return {
    lineup: repaired.lineup,
    ok: true,
    message: `${map.get(inId)?.name} in for ${map.get(outId)?.name} · ${formation}.${repaired.note ? ` ${repaired.note}` : ""}`,
  };
}

export function setArmband(lineup: Lineup, playerId: number, role: "captain" | "vice", squad: SquadPlayer[]): LineupResult {
  const name = squad.find((player) => player.id === playerId)?.name ?? "Player";
  if (!lineup.starters.includes(playerId)) return { lineup, ok: false, message: "Only starters can wear an armband." };
  if (role === "captain") {
    const vice = lineup.vice === playerId ? lineup.captain : lineup.vice;
    return { lineup: { ...lineup, captain: playerId, vice }, ok: true, message: `${name} is your simulated captain.` };
  }
  const captain = lineup.captain === playerId ? lineup.vice : lineup.captain;
  return { lineup: { ...lineup, vice: playerId, captain }, ok: true, message: `${name} is your simulated vice-captain.` };
}

export function moveBench(lineup: Lineup, index: number, offset: -1 | 1): Lineup {
  const target = index + offset;
  // Slot 0 is the substitute goalkeeper and never moves.
  if (index < 1 || target < 1 || target >= lineup.bench.length) return lineup;
  const bench = [...lineup.bench];
  [bench[index], bench[target]] = [bench[target], bench[index]];
  return { ...lineup, bench };
}

/** Derived projection: starters' model xP plus the captain's extra multiplier. */
export function projectLineup(lineup: Lineup, squad: SquadPlayer[]): { points: number | null; missing: number } {
  const map = byId(squad);
  let total = 0;
  let missing = 0;
  for (const id of lineup.starters) {
    const xp = map.get(id)?.xp;
    if (xp == null) { missing += 1; continue; }
    total += xp * (id === lineup.captain ? 2 : 1);
  }
  return { points: missing > 0 || !lineup.starters.length ? null : total, missing };
}

export function sameLineup(left: Lineup, right: Lineup): boolean {
  return left.captain === right.captain
    && left.vice === right.vice
    && [...left.starters].sort().join() === [...right.starters].sort().join()
    && left.bench.join() === right.bench.join();
}

/** Swap partners that keep the XI legal, for highlighting during tap-to-swap. */
export function validTargets(lineup: Lineup, selectedId: number, squad: SquadPlayer[]): Set<number> {
  const targets = new Set<number>();
  for (const player of squad) {
    if (player.id === selectedId) continue;
    if (swapPlayers(lineup, selectedId, player.id, squad).ok) targets.add(player.id);
  }
  return targets;
}
