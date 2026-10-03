"use client";

import { useState } from "react";

import { useTeam } from "@/app/providers/TeamProvider";
import { Segmented } from "@/components/ui/primitives";
import { MAX_FREE_TRANSFERS } from "@/lib/freeTransfers";
import type { GameweekPlan } from "@/lib/model/plan";

const COUNT_OPTIONS = Array.from({ length: MAX_FREE_TRANSFERS + 1 }, (_, index) => ({ value: String(index), label: String(index) }));

function countCopy(count: number | null, source: GameweekPlan["freeTransfersSource"]): string {
  if (count == null || source === "unknown") return "Free transfers unknown, planned as 0";
  const noun = `${count} free transfer${count === 1 ? "" : "s"}`;
  return source === "user" ? `${noun}, set by you` : `${noun}, estimated from your public transfer history`;
}

/**
 * Public FPL data cannot see every free-transfer rule, so the count is an
 * estimate the manager can correct. The plan and hit costs are rebuilt with it.
 */
export function FreeTransfersControl({ count, source }: { count: number | null; source: GameweekPlan["freeTransfersSource"] }) {
  const { setFreeTransfers, loading } = useTeam();
  const [editing, setEditing] = useState(false);

  if (!editing) {
    return (
      <span className="ft-control">
        <span>{countCopy(count, source)}</span>
        <button type="button" className="ft-link" onClick={() => setEditing(true)}>
          {source === "user" ? "Change" : "Not right? Set yours"}
        </button>
      </span>
    );
  }

  const choose = (value: number | null) => {
    setEditing(false);
    void setFreeTransfers(value);
  };

  return (
    <span className="ft-control ft-control-editing">
      <span>Free transfers in the FPL app:</span>
      <Segmented
        size="sm"
        label="Your free transfers"
        options={COUNT_OPTIONS.map((option) => ({ ...option, disabled: loading }))}
        value={source === "user" && count != null ? String(count) : ""}
        onChange={(value) => choose(Number(value))}
      />
      {source === "user" ? <button type="button" className="ft-link" onClick={() => choose(null)}>Use estimate</button> : null}
      <button type="button" className="ft-link" onClick={() => setEditing(false)}>Cancel</button>
    </span>
  );
}
