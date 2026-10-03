/**
 * The FPL-AI kit system: original, club-inspired shirts.
 *
 * Every club is represented by its colours plus one of a small family of
 * FPL-AI house patterns. Patterns are deliberately assigned so that no club
 * gets a reproduction of its real shirt layout (no Arsenal sleeves, no
 * Newcastle stripes, etc.). No crests, sponsors, maker marks or protected kit
 * details are used — only colour, geometry and the club's initials.
 */

export type KitPattern = "plain" | "chevron" | "sash" | "split" | "yoke" | "band" | "pinstripe";

export type KitDesign = {
  code: string;
  body: string;
  detail: string;
  trim: string;
  ink: string;
  pattern: KitPattern;
};

const designs: Record<string, Omit<KitDesign, "code">> = {
  ARS: { body: "#d6262f", detail: "#f4f4f4", trim: "#14254a", ink: "#ffffff", pattern: "chevron" },
  AVL: { body: "#6b1d3e", detail: "#9cc6ec", trim: "#f2c94c", ink: "#ffffff", pattern: "band" },
  BOU: { body: "#c8202b", detail: "#111317", trim: "#f4f4f4", ink: "#ffffff", pattern: "split" },
  BRE: { body: "#d9252e", detail: "#f4f4f4", trim: "#111317", ink: "#ffffff", pattern: "sash" },
  BHA: { body: "#1f5fbf", detail: "#f4f4f4", trim: "#f2c94c", ink: "#ffffff", pattern: "yoke" },
  BUR: { body: "#6c1d45", detail: "#9fd3ec", trim: "#f2c94c", ink: "#ffffff", pattern: "yoke" },
  CHE: { body: "#1747a6", detail: "#f4f4f4", trim: "#d5a838", ink: "#ffffff", pattern: "band" },
  COV: { body: "#6cb4e6", detail: "#14335a", trim: "#f4f4f4", ink: "#0f2340", pattern: "sash" },
  CRY: { body: "#1d4a9a", detail: "#c62334", trim: "#f4f4f4", ink: "#ffffff", pattern: "split" },
  EVE: { body: "#1a3d9c", detail: "#f4f4f4", trim: "#2d8a4e", ink: "#ffffff", pattern: "yoke" },
  FUL: { body: "#f4f4f4", detail: "#16181d", trim: "#c62334", ink: "#16181d", pattern: "chevron" },
  HUL: { body: "#f0a12f", detail: "#16181d", trim: "#f4f4f4", ink: "#16181d", pattern: "band" },
  IPS: { body: "#1c4fb0", detail: "#f4f4f4", trim: "#d63a3f", ink: "#ffffff", pattern: "sash" },
  LEE: { body: "#f4f4f4", detail: "#1d428a", trim: "#f2c94c", ink: "#1d428a", pattern: "yoke" },
  LEI: { body: "#1c3f95", detail: "#f4f4f4", trim: "#f2b729", ink: "#ffffff", pattern: "chevron" },
  LIV: { body: "#c51f34", detail: "#f4f4f4", trim: "#1fb3a8", ink: "#ffffff", pattern: "band" },
  MCI: { body: "#73b2e0", detail: "#1b2c59", trim: "#f4f4f4", ink: "#10203f", pattern: "chevron" },
  MUN: { body: "#d1281f", detail: "#16181d", trim: "#f4f4f4", ink: "#ffffff", pattern: "sash" },
  NEW: { body: "#16181d", detail: "#f4f4f4", trim: "#5fb7e6", ink: "#ffffff", pattern: "split" },
  NFO: { body: "#cc1e2b", detail: "#f4f4f4", trim: "#16181d", ink: "#ffffff", pattern: "yoke" },
  NOR: { body: "#f5d916", detail: "#16864a", trim: "#16181d", ink: "#123524", pattern: "sash" },
  SHU: { body: "#d9283a", detail: "#f4f4f4", trim: "#16181d", ink: "#ffffff", pattern: "band" },
  SOU: { body: "#d2232b", detail: "#f4f4f4", trim: "#16181d", ink: "#ffffff", pattern: "split" },
  SUN: { body: "#d8232f", detail: "#f4f4f4", trim: "#16181d", ink: "#ffffff", pattern: "chevron" },
  TOT: { body: "#f4f4f4", detail: "#16245a", trim: "#8d97a8", ink: "#16245a", pattern: "sash" },
  WAT: { body: "#f5dd2a", detail: "#16181d", trim: "#d6262f", ink: "#16181d", pattern: "band" },
  WHU: { body: "#7b2a3c", detail: "#5ab6e3", trim: "#f2c94c", ink: "#ffffff", pattern: "split" },
  WOL: { body: "#f2ad1f", detail: "#1f1d1e", trim: "#f4f4f4", ink: "#1f1d1e", pattern: "chevron" },
};

const aliases: Record<string, string> = {
  arsenal: "ARS", astonvilla: "AVL", bournemouth: "BOU", brentford: "BRE",
  brighton: "BHA", brightonandhovealbion: "BHA", burnley: "BUR", chelsea: "CHE",
  coventry: "COV", coventrycity: "COV", crystalpalace: "CRY", everton: "EVE",
  fulham: "FUL", hull: "HUL", hullcity: "HUL", ipswich: "IPS", ipswichtown: "IPS",
  leeds: "LEE", leedsunited: "LEE", leicester: "LEI", leicestercity: "LEI",
  liverpool: "LIV", mancity: "MCI", manchestercity: "MCI", manutd: "MUN",
  manchesterunited: "MUN", newcastle: "NEW", newcastleunited: "NEW",
  norwich: "NOR", norwichcity: "NOR", nottmforest: "NFO", nottinghamforest: "NFO",
  sheffieldutd: "SHU", sheffieldunited: "SHU", southampton: "SOU", spurs: "TOT",
  sunderland: "SUN", tottenham: "TOT", tottenhamhotspur: "TOT", watford: "WAT",
  westham: "WHU", westhamunited: "WHU", wolves: "WOL", wolverhamptonwanderers: "WOL",
};

const neutral: Omit<KitDesign, "code"> = {
  body: "#3a3f52", detail: "#8b7cf6", trim: "#c9c3ff", ink: "#ffffff", pattern: "plain",
};

/** Goalkeeper shirts share one FPL-AI palette, trimmed in the club colour. */
const GOALKEEPER_BODY = "#20c997";

export function clubCode(team?: string | null, teamShort?: string | null): string {
  const supplied = teamShort?.trim().toUpperCase() ?? "";
  if (designs[supplied]) return supplied;
  const alias = aliases[String(team ?? "").toLowerCase().replace(/[^a-z0-9]/g, "")];
  if (alias) return alias;
  return supplied || String(team ?? "").replace(/[^a-z]/gi, "").slice(0, 3).toUpperCase() || "FPL";
}

export function kitDesign(team?: string | null, teamShort?: string | null, goalkeeper = false): KitDesign {
  const code = clubCode(team, teamShort);
  const base = designs[code] ?? neutral;
  if (!goalkeeper) return { code, ...base };
  return { code, body: GOALKEEPER_BODY, detail: "#0d3b30", trim: base.body, ink: "#062a22", pattern: "pinstripe" };
}

/** A single representative colour for chips, dots and fixture cells. */
export function clubColor(team?: string | null, teamShort?: string | null): string {
  const design = kitDesign(team, teamShort);
  return design.body === "#f4f4f4" ? design.detail : design.body;
}
