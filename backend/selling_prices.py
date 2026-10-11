"""Selling prices derived from a manager's public transfer history.

The public picks endpoint does not include selling prices, but the FPL rule
is public: a player sells for his purchase price plus half of any rise
(rounded down to £0.1m), or for the current price after a fall. The purchase
price is public too:

* a player bought by transfer cost `element_in_cost` in the latest transfer
  that brought him in - except transfers made under a Free Hit, whose squad
  reverts after the deadline;
* a player kept from a GW1 squad cost his season start price, which is the
  current price minus the official `cost_change_start`.

Players whose purchase cannot be traced (a squad first picked after GW1 and
never transferred) keep the existing labelled market-price estimate.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

DERIVED_SOURCE = "derived_from_transfer_history"


def selling_price(purchase: float, current: float) -> float:
    """FPL selling price in £m from purchase and current prices in £m."""
    purchase_tenths, current_tenths = round(purchase * 10), round(current * 10)
    if current_tenths <= purchase_tenths:
        return current_tenths / 10
    return (purchase_tenths + (current_tenths - purchase_tenths) // 2) / 10


def derive_purchase_prices(
    owned_ids: Iterable[int],
    *,
    transfers: Iterable[Mapping[str, Any]],
    chips: Iterable[Mapping[str, Any]],
    elements: Iterable[Mapping[str, Any]],
    started_event: int | None,
) -> dict[int, float]:
    """Purchase price in £m for each owned player whose purchase is traceable."""
    free_hits = {
        int(chip["event"]) for chip in chips
        if str(chip.get("name", "")).lower() == "freehit" and chip.get("event") is not None
    }
    latest: dict[int, tuple[str, int, float]] = {}
    for item in transfers:
        try:
            player, event, cost = int(item["element_in"]), int(item["event"]), float(item["element_in_cost"])
        except (KeyError, TypeError, ValueError):
            continue
        if event in free_hits:
            continue
        stamp = (str(item.get("time") or ""), event)
        if player not in latest or stamp > latest[player][:2]:
            latest[player] = (stamp[0], stamp[1], cost / 10)
    by_id = {int(element["id"]): element for element in elements if element.get("id") is not None}
    prices: dict[int, float] = {}
    for player in owned_ids:
        player = int(player)
        if player in latest:
            prices[player] = latest[player][2]
            continue
        element = by_id.get(player)
        if started_event == 1 and element and element.get("now_cost") is not None \
                and element.get("cost_change_start") is not None:
            prices[player] = (int(element["now_cost"]) - int(element["cost_change_start"])) / 10
    return prices


def attach_selling_prices(
    picks: list[dict[str, Any]],
    *,
    transfers: Iterable[Mapping[str, Any]],
    chips: Iterable[Mapping[str, Any]],
    elements: Iterable[Mapping[str, Any]],
    started_event: int | None,
) -> list[dict[str, Any]]:
    """Copy of `picks` with derived purchase/selling prices where traceable."""
    elements = list(elements)
    current = {int(e["id"]): int(e["now_cost"]) / 10 for e in elements
               if e.get("id") is not None and e.get("now_cost") is not None}
    purchases = derive_purchase_prices(
        [int(pick["player_id"]) for pick in picks], transfers=list(transfers), chips=list(chips),
        elements=elements, started_event=started_event)
    result = []
    for pick in picks:
        pick = dict(pick)
        player = int(pick["player_id"])
        if pick.get("selling_price") is None and player in purchases and player in current:
            pick["purchase_price"] = purchases[player]
            pick["selling_price"] = selling_price(purchases[player], current[player])
            pick["selling_price_source"] = DERIVED_SOURCE
        result.append(pick)
    return result
