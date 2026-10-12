"use client";

import { TrendingUp } from "lucide-react";
import Link from "next/link";

import { isDrop, isRise, nextStatus } from "@/lib/fpl/prices";
import { usePriceChanges } from "@/lib/hooks/data";
import type { TransferMove } from "@/lib/model/plan";

/**
 * When to make the recommended transfer, from FPL's own price projections:
 * before tonight's change if the incoming player is about to rise or the
 * outgoing one about to drop, after it if the incoming player is about to drop.
 */
export function PriceTiming({ moves }: { moves: TransferMove[] }) {
  const prices = usePriceChanges(moves.length > 0);
  const data = prices.data?.data;
  if (!data || !moves.length) return null;
  const byId = new Map(data.players.map((player) => [player.player_id, player]));
  const at = data.next_change_at ? new Date(data.next_change_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }) : "the next price change";
  const notes: string[] = [];
  for (const move of moves) {
    const incoming = byId.get(move.inId);
    const outgoing = byId.get(move.outId);
    const inStatus = incoming ? nextStatus(incoming) : null;
    const outStatus = outgoing ? nextStatus(outgoing) : null;
    if (inStatus && isRise(inStatus)) notes.push(`${move.inName} is likely to rise tonight: buy before ${at} to pay £0.1m less.`);
    else if (inStatus && isDrop(inStatus)) notes.push(`${move.inName} is likely to drop tonight: buying after ${at} costs £0.1m less.`);
    if (outStatus && isDrop(outStatus)) notes.push(`${move.outName} is likely to drop tonight: selling before ${at} keeps more of his value.`);
  }
  if (!notes.length) return null;
  return (
    <div className="price-timing" role="note">
      <TrendingUp size={15} aria-hidden="true" />
      <div>
        {notes.map((note) => <p key={note}>{note}</p>)}
        <Link className="link" href="/prices">Price changes</Link>
      </div>
    </div>
  );
}
