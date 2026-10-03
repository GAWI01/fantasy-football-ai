import type { ReactNode } from "react";

import { Kit } from "@/components/kit/Kit";
import { clubColor } from "@/lib/fpl/kits";

/**
 * Tall matchday card: a large original kit over the club colour, the name in
 * display type and one headline number. Used for transfers and the armband.
 */
export function PlayerCard({
  name,
  team,
  teamShort,
  position,
  value,
  unit = "xP",
  meta,
  tag,
  tone = "neutral",
  badge,
}: {
  name: string;
  team?: string | null;
  teamShort?: string | null;
  position?: string | null;
  value: ReactNode;
  unit?: string;
  meta?: ReactNode;
  tag?: ReactNode;
  tone?: "neutral" | "out" | "in" | "captain";
  badge?: ReactNode;
}) {
  const goalkeeper = position === "GKP" || position === "GK";
  return (
    <div className={`pcard pcard-${tone}`} style={{ ["--club" as string]: clubColor(team, teamShort) }}>
      {tag ? <span className="pcard-tag">{tag}</span> : null}
      <span className="pcard-kit" aria-hidden="true">
        <Kit team={team} teamShort={teamShort} goalkeeper={goalkeeper} size={76} />
        {badge ? <span className="pcard-badge">{badge}</span> : null}
      </span>
      <span className="pcard-pos">{position ?? "—"}{teamShort ? ` · ${teamShort}` : ""}</span>
      <strong className="pcard-name">{name}</strong>
      <span className="pcard-value"><b>{value}</b><small>{unit}</small></span>
      {meta ? <span className="pcard-meta">{meta}</span> : null}
    </div>
  );
}
