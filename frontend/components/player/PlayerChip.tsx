import type { ReactNode } from "react";

import { Kit } from "@/components/kit/Kit";

/** Compact identity row: original club kit, name and a meta line. */
export function PlayerChip({
  name,
  team,
  teamShort,
  position,
  meta,
  end,
  size = 34,
  badge,
}: {
  name: string;
  team?: string | null;
  teamShort?: string | null;
  position?: string | null;
  meta?: ReactNode;
  end?: ReactNode;
  size?: number;
  badge?: ReactNode;
}) {
  const goalkeeper = position === "GKP" || position === "GK";
  return (
    <span className="pchip">
      <span className="pchip-kit">
        <Kit team={team} teamShort={teamShort} goalkeeper={goalkeeper} size={size} bare={size < 30} />
        {badge ? <span className="pchip-badge">{badge}</span> : null}
      </span>
      <span className="pchip-text">
        <strong>{name}</strong>
        {meta ? <small>{meta}</small> : null}
      </span>
      {end ? <span className="pchip-end">{end}</span> : null}
    </span>
  );
}
