"use client";

import { Gauge, Newspaper } from "lucide-react";
import type { ReactNode } from "react";

import { Kit } from "@/components/kit/Kit";
import { Sheet } from "@/components/ui/Sheet";
import { Meter, SourceBadge } from "@/components/ui/primitives";
import { fixed, percent, price, sentenceCase } from "@/lib/format";
import { availabilityFromStatus, POSITION_LABEL } from "@/lib/fpl/rules";
import type { SquadPlayer } from "@/lib/model/squad";

export function modelRead(player: SquadPlayer): string {
  const status = String(player.status ?? "a").toLowerCase();
  if (["i", "s", "u", "n"].includes(status)) return "Officially unavailable. Unless news improves, plan around a bench route or a transfer.";
  if (status === "d") return "Flagged as doubtful. Check the latest team news before relying on the projection.";
  if (player.risk && (player.risk.label === "HIGH" || player.risk.label === "VERY_HIGH")) return "Minutes risk is high in the model. Treat the projection as fragile and keep a playable bench option.";
  if (player.startProbability != null && player.startProbability < 0.7) return "Start probability is below 70%, so much of the value depends on being picked.";
  if (player.xmins == null || player.startProbability == null) return "Minutes forecast unavailable. The points projection alone does not establish minutes security.";
  if (player.difficulty != null && player.difficulty >= 4) return "A difficult next fixture. The five-Gameweek view matters more than this week's number.";
  if (player.xp != null && player.xp >= 6) return "A strong points projection. Check the minutes forecast and latest team news alongside it.";
  return "Compare the points and minutes forecasts with the fixture and latest team news.";
}

function Fact({ label, value, source, children }: { label: string; value: ReactNode; source?: Parameters<typeof SourceBadge>[0]["kind"]; children?: ReactNode }) {
  return (
    <div className="fact">
      <span className="fact-label">{label}{source ? <SourceBadge kind={source} /> : null}</span>
      <strong className="fact-value">{value}</strong>
      {children}
    </div>
  );
}

export function SquadPlayerDetail({ player, live }: { player: SquadPlayer; live: boolean }) {
  const availability = availabilityFromStatus(player.status, player.chance);
  const maxXp = Math.max(1, ...player.horizon.map((gameweek) => gameweek.predicted_points));
  return (
    <div className="pdetail">
      <div className="pdetail-hero">
        <Kit team={player.team} teamShort={player.teamShort} goalkeeper={player.position === "GKP"} size={64} />
        <div>
          <span className="eyebrow">{POSITION_LABEL[player.position]} · {player.team}</span>
          <div className="row row-wrap pdetail-tags">
            <span className={`pill ${availability.tone === "ok" ? "pill-pos" : availability.tone === "warn" ? "pill-warn" : availability.tone === "risk" ? "pill-neg" : ""}`}><i className={`dot dot-${availability.tone}`} />{availability.label}</span>
            {player.risk ? <span className={`pill ${player.risk.label === "LOW" ? "" : player.risk.label === "MEDIUM" ? "pill-warn" : "pill-neg"}`}>{sentenceCase(player.risk.label)} minutes risk</span> : null}
            {player.isCaptain ? <span className="pill pill-accent">Official captain</span> : player.isVice ? <span className="pill">Official vice</span> : null}
          </div>
        </div>
      </div>

      {live && player.livePoints != null ? (
        <div className="facts facts-live">
          <Fact label="Live points" value={player.livePoints} source="live" />
          <Fact label="Minutes" value={player.liveMinutes ?? "—"} source="live" />
          <Fact label="BPS" value={player.liveBps ?? "—"} source="live" />
        </div>
      ) : null}

      <div className="facts">
        <Fact label="Next GW" value={<span className="tone-accent">{fixed(player.xp)} xP</span>} source="model" />
        <Fact label="Exp. minutes" value={player.xmins == null ? "—" : Math.round(player.xmins)} source="model">
          <Meter value={player.xmins == null ? null : player.xmins / 90} label="Expected minutes out of 90" tone={player.xmins != null && player.xmins >= 70 ? "pos" : "warn"} />
        </Fact>
        <Fact label="Start chance" value={percent(player.startProbability, { fraction: true })} source="model" />
        <Fact label="Price" value={price(player.price)} source="official">{player.sellingPrice != null && player.sellingPrice !== player.price ? <small className="faint">Sells for {price(player.sellingPrice)}</small> : null}</Fact>
        <Fact label="Form" value={fixed(player.form)} source="official" />
        <Fact label="Owned by" value={percent(player.ownership, { digits: 1 })} source="official" />
      </div>

      <section className="pdetail-section">
        <h3>Fixture outlook <SourceBadge kind="model" /></h3>
        {player.horizon.length ? (
          <ol className="horizon">
            {player.horizon.map((gameweek) => {
              const blank = gameweek.fixture_count === 0;
              return (
                <li key={`${gameweek.gameweek}-${gameweek.opponent}`} className={blank ? "horizon-blank" : undefined}>
                  <span className="horizon-gw">GW{gameweek.gameweek}</span>
                  <span className={`fdr fdr-${gameweek.difficulty ? Math.round(gameweek.difficulty) : 0}`}>
                    {blank ? "Blank" : `${gameweek.opponent ?? "TBC"}${gameweek.home == null ? "" : gameweek.home ? " (H)" : " (A)"}`}
                  </span>
                  <span className="horizon-bar" aria-hidden="true"><i style={{ width: `${(gameweek.predicted_points / maxXp) * 100}%` }} /></span>
                  <span className="horizon-xp num">{fixed(gameweek.predicted_points)}{gameweek.uncertainty ? <small> ±{fixed(gameweek.uncertainty)}</small> : null}</span>
                  <span className="horizon-method">{gameweek.projection_method === "native_model" ? "Model" : blank ? "—" : "Scaled"}</span>
                </li>
              );
            })}
          </ol>
        ) : player.opponent ? (
          <p>Next: <b>{player.opponent}{player.home == null ? "" : player.home ? " (H)" : " (A)"}</b>{player.difficulty ? ` · difficulty ${player.difficulty}` : ""}</p>
        ) : <p className="faint">Fixture projection unavailable.</p>}
        {player.horizon.length ? <p className="card-note">GW+1 is the native model. Later weeks are scaled by official fixture difficulty with widening uncertainty.</p> : null}
      </section>

      <section className="pdetail-section pdetail-read">
        <Gauge size={18} aria-hidden="true" />
        <div><h3>Model read <SourceBadge kind="derived" /></h3><p>{modelRead(player)}</p></div>
      </section>

      {player.news ? (
        <section className="pdetail-section pdetail-news">
          <Newspaper size={18} aria-hidden="true" />
          <div><h3>Official news <SourceBadge kind="official" /></h3><p>{player.news}</p></div>
        </section>
      ) : null}

      <section className="pdetail-section">
        <h3>Season <SourceBadge kind="official" /></h3>
        <dl className="season-grid">
          <div><dt>Points</dt><dd>{player.seasonPoints ?? "—"}</dd></div>
          <div><dt>Starts</dt><dd>{player.starts ?? "—"}</dd></div>
          <div><dt>Goals</dt><dd>{player.goals ?? "—"}</dd></div>
          <div><dt>Assists</dt><dd>{player.assists ?? "—"}</dd></div>
          <div><dt>xG</dt><dd>{fixed(player.xg, 2)}</dd></div>
          <div><dt>xA</dt><dd>{fixed(player.xa, 2)}</dd></div>
          <div><dt>Bonus</dt><dd>{player.bonus ?? "—"}</dd></div>
          <div><dt>ICT</dt><dd>{fixed(player.ict)}</dd></div>
        </dl>
      </section>
    </div>
  );
}

export function SquadPlayerSheet({ player, open, onClose, live, actions }: { player: SquadPlayer | null; open: boolean; onClose: () => void; live: boolean; actions?: ReactNode }) {
  if (!player) return null;
  return (
    <Sheet open={open} onClose={onClose} title={player.name} subtitle={`${player.position} · ${player.teamShort} · ${price(player.price)}`} footer={actions}>
      <SquadPlayerDetail player={player} live={live} />
    </Sheet>
  );
}
