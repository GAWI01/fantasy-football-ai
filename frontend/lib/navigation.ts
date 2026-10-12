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


export type NavKey = "overview" | "team" | "plan" | "league" | "players" | "prices" | "fixtures" | "review" | "settings";

export type NavItem = {
  key: NavKey;
  href: string;
  label: string;
  short: string;
  group: "decide" | "research" | "account";
  /** One line in the phone's More menu: what you find there. */
  hint: string;
  /** A tab inside another destination; the menu shows only the parent. */
  parent?: NavKey;
};

export const NAV_ITEMS: readonly NavItem[] = [
  { key: "overview", href: "/", label: "Home", short: "Home", group: "decide", hint: "What to do this Gameweek, or your live score" },
  { key: "team", href: "/team", label: "My Team", short: "Team", group: "decide", hint: "Your squad on the pitch: try lineups, bench order and armbands" },
  { key: "plan", href: "/plan", label: "Plan & Transfers", short: "Plan", group: "decide", hint: "Transfers, captain and chips for the next deadline" },
  { key: "league", href: "/league", label: "Mini-leagues", short: "Leagues", group: "research", hint: "Your mini-league table and how your squad differs from rivals" },
  { key: "players", href: "/players", label: "Explore", short: "Explore", group: "research", hint: "Every player, price changes and fixture runs" },
  { key: "prices", href: "/prices", label: "Price changes", short: "Prices", group: "research", hint: "Who is about to rise or drop in price", parent: "players" },
  { key: "fixtures", href: "/fixtures", label: "Fixtures", short: "Fixtures", group: "research", hint: "Each club's next fixtures and clean-sheet chances", parent: "players" },
  { key: "review", href: "/review", label: "History & Review", short: "History", group: "research", hint: "Your season so far and each Gameweek against the model" },
  { key: "settings", href: "/settings", label: "Settings", short: "Settings", group: "account", hint: "Your Team ID, motion and data labels" },
];

/** The destinations in the menus: tabs such as Price changes live inside Explore. */
export const MENU_ITEMS: readonly NavItem[] = NAV_ITEMS.filter((item) => !item.parent);

/** The tabs inside one destination, the destination itself first. */
export function navTabs(parent: NavKey): NavItem[] {
  return NAV_ITEMS.filter((item) => item.key === parent || item.parent === parent);
}

/** Primary destinations on the phone tab bar; everything else lives in "More". */
export const MOBILE_PRIMARY: readonly NavKey[] = ["overview", "team", "plan", "players"];

function onPath(href: string, pathname: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** A menu destination is also active on its tabs (Explore on /prices and /fixtures). */
export function isActive(item: Pick<NavItem, "href"> & { key?: NavKey }, pathname: string | null): boolean {
  if (!pathname) return false;
  if (onPath(item.href, pathname)) return true;
  return item.key != null && NAV_ITEMS.some((child) => child.parent === item.key && onPath(child.href, pathname));
}
