/**
 * The Fantasy Football AI kit system: simple shirts drawn for this site.
 *
 * Each club is shown in its traditional, long-standing home colours (approximate
 * shades, not exact brand colours) with one generic layout: plain, vertical
 * stripes, hoops, halves, a sash or contrasting sleeves. Collar and cuffs are a
 * single colour, and the only text is the club's initials in the site's own font.
 *
 * Nothing is taken from a particular season (no prints, fades, collar shapes or
 * trim combinations), and no away kits, shorts or socks are modelled. No crests,
 * sponsors, maker logos or maker trims, league patches, league lettering or
 * shirt images from the FPL game are used. Goalkeepers share one house shirt.
 */

/** Generic club layouts, plus the house "pinstripe" kept for goalkeepers only. */
export type KitPattern = "plain" | "stripes" | "hoops" | "halves" | "sash" | "sleeves" | "pinstripe";

/** Layouts a club kit may use (everything except the goalkeeper house pattern). */
export const CLUB_KIT_PATTERNS = ["plain", "stripes", "hoops", "halves", "sash", "sleeves"] as const satisfies readonly KitPattern[];

export type KitDesign = {
  code: string;
  /** Main shirt colour. */
  body: string;
  /** Second colour: stripes, hoops, the other half or the sash. */
  detail: string;
  /** Single colour for collar and cuffs. */
  trim: string;
  /** Colour of the initials. */
  ink: string;
  pattern: KitPattern;
  /** Sleeve colour for contrasting-sleeve kits. */
  sleeves?: string;
  /** Number of equal vertical bands across the front for striped kits (default 5). */
  stripes?: 3 | 5;
};

const WHITE = "#f4f4f4";
const BLACK = "#16181d";

const designs: Record<string, Omit<KitDesign, "code">> = {
  ARS: { body: "#d6262f", detail: WHITE, sleeves: WHITE, trim: WHITE, ink: "#ffffff", pattern: "sleeves" },
  AVL: { body: "#6b1d3e", detail: "#9cc6ec", sleeves: "#9cc6ec", trim: "#9cc6ec", ink: "#ffffff", pattern: "sleeves" },
  BOU: { body: "#c8202b", detail: BLACK, trim: BLACK, ink: "#ffffff", pattern: "stripes", stripes: 5 },
  BRE: { body: "#d9252e", detail: WHITE, trim: BLACK, ink: "#ffffff", pattern: "stripes", stripes: 5 },
  BHA: { body: "#1f5fbf", detail: WHITE, trim: WHITE, ink: "#ffffff", pattern: "stripes", stripes: 5 },
  BUR: { body: "#6c1d45", detail: "#a3d5ee", sleeves: "#a3d5ee", trim: WHITE, ink: "#ffffff", pattern: "sleeves" },
  CHE: { body: "#1747a6", detail: WHITE, trim: WHITE, ink: "#ffffff", pattern: "plain" },
  COV: { body: "#62b5ea", detail: WHITE, trim: WHITE, ink: "#0f2340", pattern: "plain" },
  CRY: { body: "#1d4a9a", detail: "#c62334", trim: "#c62334", ink: "#ffffff", pattern: "stripes", stripes: 5 },
  EVE: { body: "#1a3d9c", detail: WHITE, trim: WHITE, ink: "#ffffff", pattern: "plain" },
  FUL: { body: WHITE, detail: BLACK, trim: BLACK, ink: BLACK, pattern: "plain" },
  HUL: { body: "#f39325", detail: BLACK, trim: BLACK, ink: BLACK, pattern: "plain" },
  IPS: { body: "#1c4fb0", detail: WHITE, trim: WHITE, ink: "#ffffff", pattern: "plain" },
  LEE: { body: WHITE, detail: "#1d428a", trim: "#1d428a", ink: "#1d428a", pattern: "plain" },
  LEI: { body: "#1c3f95", detail: WHITE, trim: WHITE, ink: "#ffffff", pattern: "plain" },
  LIV: { body: "#c51f34", detail: WHITE, trim: WHITE, ink: "#ffffff", pattern: "plain" },
  MCI: { body: "#7ab4e0", detail: WHITE, trim: WHITE, ink: "#10203f", pattern: "plain" },
  MUN: { body: "#d1281f", detail: BLACK, trim: BLACK, ink: "#ffffff", pattern: "plain" },
  NEW: { body: BLACK, detail: WHITE, trim: WHITE, ink: "#ffffff", pattern: "stripes", stripes: 5 },
  NFO: { body: "#cc1e2b", detail: WHITE, trim: WHITE, ink: "#ffffff", pattern: "plain" },
  NOR: { body: "#f5d916", detail: "#16864a", trim: "#16864a", ink: "#123524", pattern: "plain" },
  SHU: { body: "#d9283a", detail: WHITE, trim: WHITE, ink: "#ffffff", pattern: "stripes", stripes: 5 },
  SOU: { body: "#d2232b", detail: WHITE, trim: BLACK, ink: "#ffffff", pattern: "stripes", stripes: 5 },
  SUN: { body: "#d8232f", detail: WHITE, trim: WHITE, ink: "#ffffff", pattern: "stripes", stripes: 5 },
  TOT: { body: WHITE, detail: "#16245a", trim: "#16245a", ink: "#16245a", pattern: "plain" },
  WAT: { body: "#f5dd2a", detail: BLACK, trim: BLACK, ink: BLACK, pattern: "plain" },
  WHU: { body: "#7b2a3c", detail: "#5ab6e3", sleeves: "#5ab6e3", trim: "#7b2a3c", ink: "#ffffff", pattern: "sleeves" },
  WOL: { body: "#f7b52a", detail: "#1f1d1e", trim: "#1f1d1e", ink: "#1f1d1e", pattern: "plain" },
};

/** Every club code with its own kit. */
export const KIT_CLUB_CODES: readonly string[] = Object.keys(designs);

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

/** Goalkeeper shirts share one house palette, trimmed in the club colour. */
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
  return design.body === WHITE ? design.detail : design.body;
}
