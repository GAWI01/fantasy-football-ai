"use client";

import { ChevronLeft, ChevronRight, Crown, Info, RotateCcw, Shield, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";

import { FormationRows, PitchPlayer, PitchSurface, type ValueMode } from "@/components/pitch/Pitch";
import { PlayerChip } from "@/components/player/PlayerChip";
import { SquadPlayerSheet } from "@/components/player/SquadPlayerSheet";
import { DataState } from "@/components/states/DataState";
import { Card, Delta, Segmented, SourceBadge, Stat } from "@/components/ui/primitives";
import { fixed, sentenceCase } from "@/lib/format";
import { formationLabel } from "@/lib/fpl/rules";
import { useCockpit } from "@/lib/hooks/useCockpit";
import {
  modelLineup,
  moveBench,
  officialLineup,
  projectLineup,
  sameLineup,
  setArmband,
  swapPlayers,
  validTargets,
  type Lineup,
} from "@/lib/model/lineup";
import { isFlagged, type SquadPlayer } from "@/lib/model/squad";

export function TeamWorkspace() {
  const { ready, dashboard, loading, error, refresh, state, squad, plan } = useCockpit({ withMarket: false });
  const signature = squad.map((player) => `${player.id}:${player.slot}:${player.isCaptain ? "c" : ""}${player.isVice ? "v" : ""}`).join("|");
  const official = useMemo(() => officialLineup(squad), [squad]);
  const [lineup, setLineup] = useState<Lineup | null>(null);
  const [lineupFor, setLineupFor] = useState(signature);
  const [mode, setMode] = useState<ValueMode | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [dragId, setDragId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const messageTimer = useRef<number | null>(null);

  // A new official selection (e.g. after a refresh) resets the local simulation.
  if (lineupFor !== signature) {
    setLineupFor(signature);
    setLineup(null);
    setSelected(null);
  }
  const current = lineup ?? official;
  const byId = useMemo(() => new Map(squad.map((player) => [player.id, player])), [squad]);
  const model = useMemo(() => (plan ? modelLineup(squad, plan.modelXI, plan.bench, plan.captain, plan.vice) : null), [plan, squad]);
  const targets = useMemo(() => (selected != null ? validTargets(current, selected, squad) : new Set<number>()), [current, selected, squad]);
  const liveAvailable = Boolean(dashboard?.data.live?.picks?.length) && state.liveActive;
  const activeMode: ValueMode = mode ?? (liveAvailable ? "live" : "projected");

  useEffect(() => () => { if (messageTimer.current) window.clearTimeout(messageTimer.current); }, []);

  if (!ready || (!dashboard && loading)) return <DataState title="Loading your squad…" loading>Fetching your official picks and projections.</DataState>;
  if (!dashboard && error) return <DataState tone="error" title="Your squad could not be loaded" action={<button className="btn btn-sm btn-primary" onClick={() => void refresh()}>Try again</button>}>{error}</DataState>;
  if (!dashboard) return <DataState tone="empty" title="Connect a team first" action={<Link className="btn btn-sm btn-primary" href="/">Connect your team</Link>}>My Team shows your 15 players once you add your public FPL Team ID.</DataState>;
  if (squad.length !== 15) return <DataState tone="unavailable" title="Squad incomplete">FPL returned {squad.length} of 15 players, so the lineup simulator is disabled.</DataState>;

  const simulated = !sameLineup(current, official);
  const starters = current.starters.map((id) => byId.get(id)).filter((player): player is SquadPlayer => Boolean(player)).map((player) => ({ ...player, isStarter: true }));
  const bench = current.bench.map((id) => byId.get(id)).filter((player): player is SquadPlayer => Boolean(player)).map((player) => ({ ...player, isStarter: false }));
  const projection = projectLineup(current, squad);
  const officialProjection = projectLineup(official, squad);
  const modelProjection = model ? projectLineup(model, squad) : null;
  const selectedPlayer = selected != null ? byId.get(selected) ?? null : null;
  const detailPlayer = detailId != null ? byId.get(detailId) ?? null : null;
  const flagged = squad.filter(isFlagged);
  const locked = !state.actionsOpen;

  function flash(ok: boolean, text: string) {
    setMessage({ ok, text });
    if (messageTimer.current) window.clearTimeout(messageTimer.current);
    messageTimer.current = window.setTimeout(() => setMessage(null), 6000);
  }

  function apply(result: { lineup: Lineup; ok: boolean; message: string }) {
    if (result.ok) setLineup(result.lineup);
    flash(result.ok, result.message);
  }

  function press(player: SquadPlayer) {
    if (selected == null) { setSelected(player.id); setMessage(null); return; }
    if (selected === player.id) { setSelected(null); return; }
    if (targets.has(player.id)) {
      apply(swapPlayers(current, selected, player.id, squad));
      setSelected(null);
      return;
    }
    setSelected(player.id);
  }

  function onDragStart(event: DragEvent<HTMLElement>, player: SquadPlayer) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(player.id));
    setDragId(player.id);
    setSelected(player.id);
  }
  function onDragOver(event: DragEvent<HTMLElement>, player: SquadPlayer) {
    if (dragId != null && targets.has(player.id)) event.preventDefault();
  }
  function onDrop(event: DragEvent<HTMLElement>, player: SquadPlayer) {
    event.preventDefault();
    const source = Number(event.dataTransfer.getData("text/plain")) || dragId;
    if (source && source !== player.id) apply(swapPlayers(current, source, player.id, squad));
    setDragId(null);
    setSelected(null);
  }

  const tile = (player: SquadPlayer, benchIndex?: number) => (
    <PitchPlayer
      key={player.id}
      player={player}
      mode={activeMode}
      captainId={current.captain}
      viceId={current.vice}
      selected={selected === player.id}
      target={selected != null && targets.has(player.id)}
      dimmed={selected != null && selected !== player.id && !targets.has(player.id)}
      benchIndex={benchIndex}
      onPress={press}
      draggable
      onDragStart={onDragStart}
      onDragEnd={() => { setDragId(null); }}
      onDragOver={onDragOver}
      onDrop={onDrop}
    />
  );

  return (
    <div className="team-page">
      <header className="page-head">
        <div>
          <span className="eyebrow">{dashboard.data.team.name} · GW{activeMode === "live" ? state.currentEvent : state.targetEvent ?? state.currentEvent}</span>
          <h1>My Team</h1>
          <p>Tap or drag players to test lineups, bench order and armbands. {locked ? "The deadline has passed, so this is a what-if view only." : "Changes stay in FPL-AI; set your real team in the official app."}</p>
        </div>
        <div className="page-head-actions">
          <Segmented<ValueMode>
            label="Points shown"
            value={activeMode}
            onChange={setMode}
            options={[
              { value: "projected", label: "Projected" },
              { value: "live", label: "Live", disabled: !dashboard.data.live?.picks?.length },
            ]}
          />
        </div>
      </header>

      <div className="team-summary card">
        <Stat size="md" label={<>{simulated ? "Simulated XI" : "Your XI"}</>} value={fixed(projection.points)} unit="xP" source={simulated ? "derived" : "model"} sub={`${formationLabel(starters)} · incl. captain`} />
        <Stat size="md" label="vs official" value={<Delta value={projection.points != null && officialProjection.points != null ? projection.points - officialProjection.points : null} />} sub={simulated ? "Your edits" : "No edits yet"} />
        <Stat size="md" label="Model best XI" value={fixed(modelProjection?.points)} unit="xP" source="model" sub={plan?.formation ?? "Unavailable"} />
        <div className="team-summary-actions">
          {model ? <button type="button" className="btn btn-sm" onClick={() => { setLineup(model); setSelected(null); flash(true, "Model lineup, bench order and armbands applied."); }} disabled={sameLineup(current, model)}><Sparkles size={14} aria-hidden="true" />Apply model XI</button> : null}
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => { setLineup(null); setSelected(null); flash(true, "Back to your official lineup."); }} disabled={!simulated}><RotateCcw size={14} aria-hidden="true" />Reset</button>
        </div>
      </div>

      <div className="team-layout">
        <div className="team-main">
          {simulated ? <p className="sim-banner" role="note"><Info size={14} aria-hidden="true" />Simulation. Not saved to FPL.</p> : null}
          <div aria-live="polite" className="sr-only">{message?.text}</div>
          {message ? <p className={`toast ${message.ok ? "toast-ok" : "toast-err"}`} role={message.ok ? undefined : "alert"}>{message.text}</p> : null}
          <PitchSurface label={`Starting eleven, ${activeMode === "live" ? "live points" : "projected points"}`}>
            <FormationRows starters={starters} render={(player) => tile(player)} />
          </PitchSurface>
          <div className="bench">
            <div className="bench-head">
              <span className="eyebrow">Bench · auto-sub order</span>
              <span className="faint bench-hint">Use the arrows to reorder</span>
            </div>
            <div className="bench-row">
              {bench.map((player, index) => (
                <div className="bench-slot" key={player.id}>
                  <span className="bench-order">{index === 0 ? "GK" : index}</span>
                  {tile(player, index)}
                  {index > 0 ? (
                    <div className="bench-move">
                      <button type="button" aria-label={`Move ${player.name} earlier on the bench`} disabled={index <= 1} onClick={() => setLineup(moveBench(current, index, -1))}><ChevronLeft size={14} aria-hidden="true" /></button>
                      <button type="button" aria-label={`Move ${player.name} later on the bench`} disabled={index >= bench.length - 1} onClick={() => setLineup(moveBench(current, index, 1))}><ChevronRight size={14} aria-hidden="true" /></button>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
          <p className="team-help faint">Desktop: drag a player onto a highlighted teammate. Touch: tap a player, then tap a highlighted teammate to swap. Formations stay legal (1 GK, 3–5 DEF, 2–5 MID, 1–3 FWD).</p>
        </div>

        <aside className="team-aside">
          <Card title="Armband" icon={<Crown size={16} />} source={simulated ? "derived" : "official"}>
            <div className="list">
              {[current.captain, current.vice].map((id, index) => {
                const player = id != null ? byId.get(id) : null;
                return (
                  <div className="list-row" key={index}>
                    {player ? <PlayerChip name={player.name} team={player.team} teamShort={player.teamShort} position={player.position} badge={index === 0 ? "C" : "V"} meta={index === 0 ? "Captain" : "Vice-captain"} size={32} /> : <span className="faint">Not set</span>}
                    <span className="list-row-end"><b className="tone-accent num">{fixed(player?.xp)}</b><small>xP</small></span>
                  </div>
                );
              })}
            </div>
            {plan?.captain && current.captain !== plan.captain.id ? (
              <p className="card-note">Model captain: <b>{plan.captain.name}</b> ({fixed(plan.captain.xp)} xP).</p>
            ) : plan?.captain ? <p className="card-note">Matches the model captain.</p> : null}
          </Card>

          <Card title="Squad watch" icon={<Shield size={16} />} source={["official", "model"]}>
            {flagged.length ? (
              <div className="list">
                {flagged.map((player) => (
                  <button type="button" className="list-row list-button" key={player.id} onClick={() => setDetailId(player.id)}>
                    <PlayerChip name={player.name} team={player.team} teamShort={player.teamShort} position={player.position} size={30} meta={player.news || (player.risk ? `${sentenceCase(player.risk.label)} minutes risk` : "Flagged")} />
                    <span className="list-row-end"><b className="num">{player.xmins == null ? "—" : Math.round(player.xmins)}</b><small>xMins</small></span>
                  </button>
                ))}
              </div>
            ) : <p className="muted">No flagged players. Everyone is available with a stable minutes outlook.</p>}
          </Card>
        </aside>
      </div>

      {selectedPlayer ? (
        <div className="action-bar" role="region" aria-label={`Actions for ${selectedPlayer.name}`}>
          <div className="action-bar-who">
            <strong>{selectedPlayer.name}</strong>
            <small>{targets.size ? "Tap a highlighted player to swap" : "No legal swap from here"}</small>
          </div>
          <div className="action-bar-buttons">
            <button type="button" className="btn btn-sm" onClick={() => { setDetailId(selectedPlayer.id); }}>Details</button>
            {current.starters.includes(selectedPlayer.id) ? (
              <>
                <button type="button" className="btn btn-sm" disabled={current.captain === selectedPlayer.id} onClick={() => { apply(setArmband(current, selectedPlayer.id, "captain", squad)); setSelected(null); }}>Captain</button>
                <button type="button" className="btn btn-sm" disabled={current.vice === selectedPlayer.id} onClick={() => { apply(setArmband(current, selectedPlayer.id, "vice", squad)); setSelected(null); }}>Vice</button>
              </>
            ) : null}
            <button type="button" className="icon-btn" aria-label="Cancel selection" onClick={() => setSelected(null)}><X size={16} aria-hidden="true" /></button>
          </div>
        </div>
      ) : null}

      <SquadPlayerSheet
        player={detailPlayer}
        open={detailPlayer != null}
        onClose={() => setDetailId(null)}
        live={activeMode === "live"}
        actions={detailPlayer && current.starters.includes(detailPlayer.id) ? (
          <>
            <button type="button" className="btn btn-sm" disabled={current.captain === detailPlayer.id} onClick={() => { apply(setArmband(current, detailPlayer.id, "captain", squad)); setDetailId(null); setSelected(null); }}>Make captain</button>
            <button type="button" className="btn btn-sm" disabled={current.vice === detailPlayer.id} onClick={() => { apply(setArmband(current, detailPlayer.id, "vice", squad)); setDetailId(null); setSelected(null); }}>Make vice</button>
            <SourceBadge kind="derived" label="Simulation only" />
          </>
        ) : undefined}
      />
    </div>
  );
}
