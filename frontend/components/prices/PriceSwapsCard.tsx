"use client";

import { ArrowRight, TrendingUp } from "lucide-react";

import { DataState } from "@/components/states/DataState";
import { Card, Skeleton } from "@/components/ui/primitives";
import { Term } from "@/components/ui/Term";
import type { PriceSwap } from "@/lib/contracts";
import { fixed, price, signed } from "@/lib/format";
import { isDrop, isRise, PRICE_STATUS_LABEL, statusFromLikelihood } from "@/lib/fpl/prices";
import { usePriceSwaps } from "@/lib/hooks/data";

function PriceTag({ likelihood }: { likelihood: number }) {
  const status = statusFromLikelihood(likelihood);
  if (!isRise(status) && !isDrop(status)) return <span className="swap-tag faint">Price steady</span>;
  return <span className={`swap-tag ${isRise(status) ? "tone-pos" : "tone-neg"}`}>{PRICE_STATUS_LABEL[status]}</span>;
}

function SwapRow({ swap, horizon }: { swap: PriceSwap; horizon: number }) {
  return (
    <li className="swap-row">
      <div className="swap-players">
        <span className="swap-side"><b>{swap.player_out}</b><small>Sell {price(swap.sell_price)}</small><PriceTag likelihood={swap.out_likelihood} /></span>
        <ArrowRight size={18} className="swap-arrow" aria-label="replaced by" />
        <span className="swap-side"><b>{swap.player_in}</b><small>Buy {price(swap.buy_price)}</small><PriceTag likelihood={swap.in_likelihood} /></span>
      </div>
      <p className="swap-points">
        <b className={swap.projected_net_gain >= 0 ? "tone-pos" : undefined}>{signed(swap.projected_net_gain)} points</b> over the next {horizon} Gameweeks
        {" "}· {signed(swap.next_gw_gain)} next Gameweek · {swap.hit_cost ? <span className="tone-neg">costs a −{swap.hit_cost} hit</span> : "uses a free transfer"}
      </p>
    </li>
  );
}

/**
 * Swaps that sell a player FPL expects to fall, or buy one it expects to rise,
 * without losing points. Points come first; price is the tie-breaker.
 */
export function PriceSwapsCard({ teamId, freeTransfers, recommended, collapsible = false }: {
  teamId: string | null;
  freeTransfers?: number | null;
  /** The plan's own pick, to compare against: a swap uses the same transfer. */
  recommended?: { label: string; decisionScore: number } | null;
  collapsible?: boolean;
}) {
  const swaps = usePriceSwaps(teamId, Boolean(teamId), freeTransfers);
  const data = swaps.data?.data;
  const horizon = data?.horizon ?? 5;
  const best = data?.swaps[0];
  const pickIsBetter = recommended && best && recommended.decisionScore > best.decision_score + 0.05;
  return (
    <Card id="price-swaps" title="Price-smart swaps" eyebrow="Sell before a drop, buy before a rise" icon={<TrendingUp size={16} />} source={["model", "official"]}
      collapse={collapsible ? { id: "plan-price-swaps", defaults: { mobile: false, desktop: true }, summary: best ? `${best.player_out} → ${best.player_in} · ${signed(best.projected_net_gain)} points` : "Swaps that keep your points and catch a price rise" } : undefined}>
      <p className="card-lede">Swaps that keep your points, or add some, while selling a player who is likely to drop in price or buying one who is likely to rise.</p>
      {swaps.loading && !data ? <Skeleton lines={4} /> : null}
      {swaps.error && !data ? <DataState compact tone="error" title="Price-smart swaps are unavailable" action={<button className="btn btn-sm" onClick={swaps.reload}>Try again</button>}>{swaps.error}</DataState> : null}
      {data ? (
        data.swaps.length ? (
          <ul className="swap-list">{data.swaps.map((swap) => <SwapRow key={`${swap.player_out_id}-${swap.player_in_id}`} swap={swap} horizon={horizon} />)}</ul>
        ) : (
          <DataState compact tone="empty" title="No price-smart swap right now">
            {data.risers_considered ? "None of the players likely to rise would keep your points." : "FPL expects no player you could afford to rise in the next two nights."}
          </DataState>
        )
      ) : null}
      {data?.owned_fallers.length ? (
        <p className="price-alert"><b>Likely to drop in your squad:</b> {data.owned_fallers.map((player) => player.name).join(", ")}. Selling only pays if the replacement scores as well.</p>
      ) : null}
      {pickIsBetter ? (
        <p className="card-note"><b>Our pick is worth more this week:</b> {recommended.label}. A swap here uses the same <Term k="freeTransfer">free transfer</Term>, so choose these only if you have one to spare.</p>
      ) : null}
      <details className="card-more">
        <summary>How is this worked out?</summary>
        <p className="card-note">
          Price likelihoods are FPL&apos;s own projections for the next two price changes. Each swap is scored on the same planner as our pick, over {horizon} Gameweeks;
          swaps that lose more than {fixed(Math.abs(data?.point_floor ?? 0.5), 1)} points are never shown. A rise is only £0.1m, and when you sell FPL gives you half of any rise,
          so points always come first and price only decides between close options.
        </p>
      </details>
    </Card>
  );
}
