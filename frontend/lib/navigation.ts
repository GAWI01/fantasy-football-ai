const LEGACY_MODULE_TARGETS: Readonly<Record<string, string>> = {
  "my-team": "/team",
  "transfer-center": "/plan#transfers",
  "ai-recommendations": "/plan#why",
  players: "/players",
  fixtures: "/fixtures",
  chips: "/plan#chips",
  statistics: "/review",
  "team-history": "/review",
  history: "/review",
  settings: "/settings",
};


export function legacyModuleTarget(module: string): string | null {
  return LEGACY_MODULE_TARGETS[module] ?? null;
}


export type NavKey = "overview" | "team" | "plan" | "players" | "fixtures" | "review" | "settings";

export type NavItem = {
  key: NavKey;
  href: string;
  label: string;
  short: string;
  group: "decide" | "research" | "account";
};

export const NAV_ITEMS: readonly NavItem[] = [
  { key: "overview", href: "/", label: "Overview", short: "Overview", group: "decide" },
  { key: "team", href: "/team", label: "My Team", short: "Team", group: "decide" },
  { key: "plan", href: "/plan", label: "Plan & Transfers", short: "Plan", group: "decide" },
  { key: "players", href: "/players", label: "Players", short: "Players", group: "research" },
  { key: "fixtures", href: "/fixtures", label: "Fixtures", short: "Fixtures", group: "research" },
  { key: "review", href: "/review", label: "History & Review", short: "History", group: "research" },
  { key: "settings", href: "/settings", label: "Settings", short: "Settings", group: "account" },
];

/** Primary destinations on the phone tab bar; everything else lives in "More". */
export const MOBILE_PRIMARY: readonly NavKey[] = ["overview", "team", "plan", "players"];

export function isActive(item: Pick<NavItem, "href">, pathname: string | null): boolean {
  if (!pathname) return false;
  if (item.href === "/") return pathname === "/";
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}
