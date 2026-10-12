"use client";

import { TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";

import { FormationRows, PitchPlayer, PitchSurface } from "@/components/pitch/Pitch";
import { DataState } from "@/components/states/DataState";
import { Sheet } from "@/components/ui/Sheet";
import { Segmented, Skeleton, SourceBadge, SourceScope } from "@/components/ui/primitives";
import type { ChipSquad, ChipSquadPlayer, PlayerSummary } from "@/lib/contracts";
import { fixed, price, signed } from "@/lib/format";
import { useChipSquads, useMarketProjections } from "@/lib/hooks/data";
import { incomingSquadPlayer, type SquadPlayer } from "@/lib/model/squad";

export type ChipSquadKind = "free_hit" | "wildcard";
const LABEL: Record<ChipSquadKind, string> = { free_hit: "Free Hit", wildcard: "Wildcard" };

function toSquadPlayer(player: ChipSquadPlayer, squad: ChipSquad, market: Map<number, PlayerSummary>): SquadPlayer | null {
  const model = incomingSquadPlayer(
    { player_id: player.player_id, name: player.name, position: player.position, team: player.team, price: player.price, predicted_points: player.predicted_points },
    market.get(player.player_id),
  );
  if (!model) return null;
  return {
    ...model,
    isStarter: player.starter,
    isCaptain: squad.captain_id === player.player_id,
    isVice: squad.vice_captain_id === player.player_id,
  };
}

function SquadView({ kind, squad, market, chipStatus, preferRisers }: { kind: ChipSquadKind; squad: ChipSquad; market: Map<number, PlayerSummary>; chipStatus: "available" | "used" | "unknown"; preferRisers: boolean }) {
  const players = useMemo(() => new Map((squad.players ?? []).map((player) => [player.player_id, player])), [squad.players]);
  const pick = (ids: number[] | undefined) => (ids ?? [])
    .map((id) => players.get(id))
    .filter((player): player is ChipSquadPlayer => Boolean(player))
    .map((player) => toSquadPlayer(player, squad, market))
    .filter((player): player is SquadPlayer => Boolean(player));
  const starters = pick(squad.starting_xi_ids);
  const bench = pick(squad.bench_ids);
  const incoming = (squad.players_in ?? []).map((id) => players.get(id)?.name).filter(Boolean);
  const weekGain = squad.projected_points != null && squad.current_projected_points != null ? squad.projected_points - squad.current_projected_points : null;
  const shownGain = kind === "wildcard" ? squad.gain : weekGain;

  return (
    <SourceScope kinds={["model", "derived"]}>
      <div className="chip-squad">
        {chipStatus === "used" ? <DataState compact tone="unavailable" title={`${LABEL[kind]} already used`}>Shown for reference: this is the team it would build now.</DataState> : null}
        <dl className="metrics chip-squad-metrics">
          <div>
            <dt>Next GW <SourceBadge kind="model" pinned /></dt>
            <dd>{fixed(squad.projected_points)} <small>xP</small></dd>
          </div>
          <div>
            <dt>Your team</dt>
            <dd>{fixed(squad.current_projected_points)} <small>xP</small></dd>
          </div>
          <div>
            <dt>{kind === "wildcard" ? "5-GW gain" : "Gain"} <SourceBadge kind="derived" pinned /></dt>
            <dd className={(shownGain ?? 0) > 0 ? "tone-pos" : undefined}>{signed(shownGain)} <small>xP</small></dd>
          </div>
          <div>
            <dt>Cost</dt>
            <dd>{price(squad.cost)} <small>of {price(squad.budget)}</small></dd>
          </div>
        </dl>
        <PitchSurface compact label={`Best ${LABEL[kind]} starting eleven with projected points`}>
          <FormationRows starters={starters} render={(player) => <PitchPlayer key={player.id} player={player} mode="projected" size="sm" captainId={squad.captain_id} viceId={squad.vice_captain_id} />} />
        </PitchSurface>
        <div className="bench bench-compact">
          <div className="bench-head"><span className="eyebrow">Bench order</span></div>
          <div className="bench-row">{bench.map((player, index) => <PitchPlayer key={player.id} player={player} mode="projected" size="sm" benchIndex={index} captainId={-1} viceId={-1} />)}</div>
        </div>
        <p className="card-note">
          {incoming.length ? <><b>{incoming.length} new:</b> {incoming.join(", ")}. </> : "No changes: your squad is already the best. "}
          {kind === "free_hit"
            ? "A Free Hit team plays one Gameweek, then your own squad returns, so it is picked for next Gameweek only."
            : "A Wildcard team is kept, so it is picked for the next five Gameweeks (later weeks count less); next Gameweek's lineup is shown."}
          {" "}Budget: your bank plus your players&apos; selling prices.
        </p>
        {kind === "wildcard" ? <PriceLine squad={squad} preferRisers={preferRisers} /> : null}
      </div>
    </SourceScope>
  );
}

/** Which Wildcard picks FPL projects to rise or drop in price over the next two nights. */
function PriceLine({ squad, preferRisers }: { squad: ChipSquad; preferRisers: boolean }) {
  const players = squad.players ?? [];
  const risers = players.filter((player) => (player.price_likelihood ?? 0) >= 4).map((player) => player.name);
  const fallers = players.filter((player) => (player.price_likelihood ?? 0) <= -4).map((player) => player.name);
  if (!risers.length && !fallers.length) {
    return <p className="card-note">{preferRisers ? "No near-equal choice had a likely price rise this time, so the squad is unchanged." : "None of these players is likely to change price in the next two nights."}</p>;
  }
  return (
    <p className="price-timing chip-price-line">
      <TrendingUp size={15} aria-hidden="true" />
      <span>
        {risers.length ? <><b className="tone-pos">Likely to rise:</b> {risers.join(", ")}. </> : null}
        {fallers.length ? <><b className="tone-neg">Likely to drop:</b> {fallers.join(", ")}. </> : null}
        {preferRisers ? "Price risers win ties; points always come first." : "Turn on “Prioritise price risers” to prefer risers between near-equal players."}
      </span>
    </p>
  );
}

/** The best Free Hit and Wildcard squads, fetched when the sheet opens. */
export function ChipSquadSheet({ open, onClose, kind, onKind, teamId, chipStatus }: {
  open: boolean;
  onClose: () => void;
  kind: ChipSquadKind;
  onKind: (kind: ChipSquadKind) => void;
  teamId: string | null;
  chipStatus: Record<ChipSquadKind, "available" | "used" | "unknown">;
}) {
  // Price rises only matter for a squad you keep, so the option is Wildcard-only.
  const [preferRisers, setPreferRisers] = useState(false);
  const squads = useChipSquads(teamId, open, preferRisers && kind === "wildcard");
  const market = useMarketProjections(open);
  const squad = squads.data?.data[kind];
  return (
    <Sheet open={open} onClose={onClose} title={`Best ${LABEL[kind]} team`} subtitle={squads.data?.meta.event ? `For GW${squads.data.meta.event}` : undefined} size="lg">
      <div className="chip-squad-controls">
        <Segmented<ChipSquadKind> label="Chip" value={kind} onChange={onKind} options={[{ value: "free_hit", label: "Free Hit" }, { value: "wildcard", label: "Wildcard" }]} />
        {kind === "wildcard" ? (
          <label className="check" title="Between near-equal players, pick the one FPL projects to rise in price and avoid likely fallers">
            <input type="checkbox" checked={preferRisers} onChange={(event) => setPreferRisers(event.target.checked)} />
            <span>Prioritise price risers</span>
          </label>
        ) : null}
      </div>
      {squads.loading && !squads.data ? <><p className="muted">Building the best squads within your budget…</p><Skeleton lines={8} /></> : null}
      {squads.error && !squads.data ? <DataState tone="error" title="The chip squads could not be built" action={<button className="btn btn-sm" onClick={squads.reload}>Try again</button>}>{squads.error}</DataState> : null}
      {squad && squad.available ? <SquadView kind={kind} squad={squad} market={market.byId} chipStatus={chipStatus[kind]} preferRisers={kind === "wildcard" && preferRisers} /> : null}
      {squad && !squad.available ? <DataState tone="unavailable" title="No squad found">The search did not finish ({squad.status ?? "unknown"}). Try again in a moment.</DataState> : null}
      {squads.data && !squads.data.data.selling_prices_known ? <p className="card-note">Selling prices are estimated from your public transfer history. Check them in FPL before you spend.</p> : null}
    </Sheet>
  );
}
