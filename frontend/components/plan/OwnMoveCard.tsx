"use client";

import { FlaskConical } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import { Card, Delta, SourceBadge } from "@/components/ui/primitives";
import { fetchEvaluation } from "@/lib/api";
import type { EvaluationEnvelope, PlayerSummary } from "@/lib/contracts";
import { normalizePosition, POSITION_LABEL } from "@/lib/fpl/rules";
import { fixed, price, signed } from "@/lib/format";
import type { GameweekPlan } from "@/lib/model/plan";
import type { SquadPlayer } from "@/lib/model/squad";

type Result = EvaluationEnvelope["data"];

/** Plain-language comparison with holding and with the recommendation. */
export function ownMoveVerdict(result: Result): string {
  if (!result.legal || !result.option) return result.reason ?? "This move is not allowed.";
  const score = result.option.decision_score ?? 0;
  const recommended = result.recommended.decision_score ?? 0;
  const recommendsHold = !result.recommended.transfers.length;
  if (score <= 0) {
    const why = "its gain does not cover the value of the free transfer it uses";
    return recommendsHold
      ? `Worse than holding by ${fixed(Math.abs(score))} points: ${why}. Hold, as the plan recommends.`
      : `Worse than holding by ${fixed(Math.abs(score))} points: ${why}. The recommended plan scores ${signed(recommended)}.`;
  }
  if (score >= recommended - 0.05) {
    return recommendsHold
      ? "Better than holding, so this beats the plan."
      : "As good as the recommended plan.";
  }
  return `Better than holding by ${fixed(score)}, but ${fixed(recommended - score)} below the recommended plan.`;
}

export function OwnMoveCard({
  teamId,
  plan,
  squad,
  market,
}: {
  teamId: string;
  plan: GameweekPlan;
  squad: SquadPlayer[];
  market: Map<number, PlayerSummary>;
}) {
  const [sellId, setSellId] = useState<number | null>(null);
  const [buyId, setBuyId] = useState<number | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selling = squad.find((player) => player.id === sellId) ?? null;
  const owned = useMemo(() => new Set(squad.map((player) => player.id)), [squad]);
  const candidates = useMemo(() => {
    if (!selling) return [];
    return [...market.values()]
      .filter((player) => !owned.has(player.player_id) && normalizePosition(player.position) === selling.position)
      .filter((player) => String(player.status ?? "a").toLowerCase() !== "u")
      .sort((left, right) => (right.predicted_points ?? -1) - (left.predicted_points ?? -1))
      .slice(0, 60);
  }, [market, owned, selling]);
  const budget = selling ? (plan.bank ?? 0) + (selling.sellingPrice ?? selling.price ?? 0) : null;

  async function evaluate(event: FormEvent) {
    event.preventDefault();
    if (sellId == null || buyId == null) return;
    setLoading(true);
    setError(null);
    try {
      const override = plan.freeTransfersSource === "user" ? plan.freeTransfers : null;
      setResult((await fetchEvaluation(teamId, [sellId], [buyId], override)).data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not evaluate this move");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const option = result?.legal ? result.option : null;
  return (
    <Card id="test-move" title="Test your own move" eyebrow="What-if" icon={<FlaskConical size={16} />} source="model">
      <form className="own-move" onSubmit={evaluate}>
        <label className="select-label">
          Sell
          <select className="select" value={sellId ?? ""} onChange={(event) => { setSellId(event.target.value ? Number(event.target.value) : null); setBuyId(null); setResult(null); }}>
            <option value="">Choose a player</option>
            {squad.map((player) => (
              <option key={player.id} value={player.id}>{player.name} · {player.position} · {price(player.sellingPrice ?? player.price)}</option>
            ))}
          </select>
        </label>
        <label className="select-label">
          Buy
          <select className="select" value={buyId ?? ""} disabled={!selling} onChange={(event) => { setBuyId(event.target.value ? Number(event.target.value) : null); setResult(null); }}>
            <option value="">{selling ? `Choose a ${POSITION_LABEL[selling.position].toLowerCase()}` : "Choose who to sell first"}</option>
            {candidates.map((player) => (
              <option key={player.player_id} value={player.player_id}>
                {player.name} · {player.team_short} · {price(player.price)} · {fixed(player.predicted_points)} xP{budget != null && (player.price ?? 0) > budget + 1e-9 ? " · over budget" : ""}
              </option>
            ))}
          </select>
        </label>
        <button className="btn btn-sm" type="submit" disabled={sellId == null || buyId == null || loading}>{loading ? "Scoring…" : "Score this move"}</button>
      </form>
      {error ? <p className="connect-error" role="alert">{error}</p> : null}
      {result ? (
        <div className="own-move-result" aria-live="polite">
          <p><b>{ownMoveVerdict(result)}</b></p>
          {option ? (
            <dl className="metrics">
              <div><dt>Next GW</dt><dd><Delta value={option.next_gw_gain ?? null} unit=" xP" /></dd></div>
              <div><dt>5-GW gain</dt><dd><Delta value={option.gross_gain ?? option.horizon_gain} unit=" xP" /></dd></div>
              <div><dt>Hit cost</dt><dd className={option.hit_cost ? "tone-neg" : undefined}>{option.hit_cost ? `−${option.hit_cost}` : "Free"}</dd></div>
              <div><dt>Score vs hold</dt><dd>{signed(option.decision_score ?? 0)}</dd></div>
            </dl>
          ) : null}
          <p className="card-note">Scored exactly like the recommendation: your best XI and captain over five weighted Gameweeks, minus any hit and the value of the free transfer you use. <SourceBadge kind="model" /></p>
        </div>
      ) : <p className="card-note">Pick a player to sell and one to buy. The engine scores your move on the same scale as its own plan.</p>}
    </Card>
  );
}
