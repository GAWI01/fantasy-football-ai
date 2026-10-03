"use client";

import {
  CalendarRange,
  History,
  LayoutDashboard,
  Menu,
  RefreshCw,
  Repeat2,
  Settings,
  Shirt,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { useTeam } from "@/app/providers/TeamProvider";
import { BrandMark } from "@/components/shell/BrandMark";
import { DeadlineCountdown } from "@/components/shell/DeadlineCountdown";
import { Sheet } from "@/components/ui/Sheet";
import { compact, relativeAge } from "@/lib/format";
import { deriveGameState, type GameState } from "@/lib/model/phase";
import { isActive, MOBILE_PRIMARY, NAV_ITEMS, type NavKey } from "@/lib/navigation";


const ICONS: Record<NavKey, LucideIcon> = {
  overview: LayoutDashboard,
  team: Shirt,
  plan: Repeat2,
  players: Users,
  fixtures: CalendarRange,
  review: History,
  settings: Settings,
};


function PhaseChip({ state, connected }: { state: GameState; connected: boolean }) {
  if (!connected) return <span className="phase-chip phase-setup">Connect a team</span>;
  if (state.phase === "live") {
    return <span className="phase-chip phase-live"><i aria-hidden="true" />GW{state.currentEvent ?? "—"} live</span>;
  }
  if (state.phase === "decision") {
    return <span className="phase-chip phase-decision"><i aria-hidden="true" />GW{state.targetEvent ?? "—"} plan open</span>;
  }
  return <span className="phase-chip phase-settled"><i aria-hidden="true" />GW{state.currentEvent ?? "—"} settled</span>;
}


function Freshness({ generatedAt, stale }: { generatedAt: string | null; stale: boolean }) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    const first = window.setTimeout(() => setNow(Date.now()), 0);
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => { window.clearTimeout(first); window.clearInterval(timer); };
  }, []);
  if (!generatedAt || now == null) return null;
  return (
    <span className={`freshness${stale ? " freshness-stale" : ""}`} title={new Date(generatedAt).toLocaleString()}>
      {stale ? "Cached data · " : "Updated "}{relativeAge(generatedAt, now)}
    </span>
  );
}


export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { dashboard, teamId, loading, refresh } = useTeam();
  const [moreOpen, setMoreOpen] = useState(false);
  const state = deriveGameState(dashboard);
  const team = dashboard?.data.team;
  const connected = Boolean(dashboard);
  // While a Gameweek is live the useful countdown is the next deadline, not the one that just passed.
  const liveNext = state.liveActive ? dashboard?.data.live : null;
  const deadlineEvent = liveNext?.next_deadline_time ? liveNext.next_event ?? null : state.targetEvent ?? dashboard?.data.live?.next_event ?? null;
  const deadlineTime = liveNext?.next_deadline_time ?? state.deadline;
  const showDeadline = connected && deadlineTime && state.phase !== "settled" ? deadlineTime : null;
  const mobileItems = NAV_ITEMS.filter((item) => MOBILE_PRIMARY.includes(item.key));
  const moreItems = NAV_ITEMS.filter((item) => !MOBILE_PRIMARY.includes(item.key));
  const moreActive = moreItems.some((item) => isActive(item, pathname));

  return (
    <div className="app" data-phase={connected ? state.phase : "setup"}>
      <a className="skip-link" href="#main-content">Skip to content</a>

      <header className="masthead">
        <div className="masthead-row">
          <Link href="/" className="brand" aria-label="Fantasy Football AI overview. Made by gawi">
            <BrandMark size={34} />
            <span className="brand-text"><strong><span className="brand-full">Fantasy Football<em>·</em>AI</span><span className="brand-short" aria-hidden="true">FF<em>·</em>AI</span></strong><small><span className="brand-tagline">Gameweek intelligence</span><span className="brand-credit">Made by <b>gawi</b></span></small></span>
          </Link>
          <nav className="topnav" aria-label="Primary">
            {NAV_ITEMS.filter((item) => item.key !== "settings").map((item) => {
              const Icon = ICONS[item.key];
              const active = isActive(item, pathname);
              return (
                <Link key={item.key} href={item.href} className="topnav-link" aria-current={active ? "page" : undefined}>
                  <Icon size={16} aria-hidden="true" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
            <Link href="/settings" className="topnav-link topnav-icon" aria-current={pathname === "/settings" ? "page" : undefined} aria-label="Settings" title="Settings">
              <Settings size={16} aria-hidden="true" />
              <span className="sr-only">Settings</span>
            </Link>
          </nav>
          <div className="masthead-end">
            {team ? (
              <Link href="/settings" className="team-badge" aria-label={`Connected team ${team.name}. Open settings`}>
                <span className="team-badge-mark" aria-hidden="true">{team.name.slice(0, 2).toUpperCase()}</span>
                <span className="team-badge-text"><strong>{team.name}</strong><small>{team.overall_rank ? `OR ${compact(team.overall_rank)}` : `Team ${teamId}`}</small></span>
              </Link>
            ) : null}
          </div>
        </div>
        <div className="statusbar">
          <PhaseChip state={state} connected={connected} />
          {showDeadline ? <DeadlineCountdown deadline={showDeadline} event={deadlineEvent} /> : null}
          <div className="statusbar-end">
            {connected ? <Freshness generatedAt={state.generatedAt} stale={state.stale} /> : null}
            {connected ? (
              <button type="button" className="icon-btn" onClick={() => void refresh()} disabled={loading} aria-label={loading ? "Refreshing data" : "Refresh data"} title="Refresh data">
                <RefreshCw size={16} aria-hidden="true" className={loading ? "spin" : undefined} />
              </button>
            ) : null}
          </div>
        </div>
      </header>

      {dashboard?.meta.degraded ? (
        <div className={`banner ${state.stale ? "banner-stale" : "banner-warn"}`} role="status">
          {state.stale
            ? "The official FPL service is not responding. You are looking at the last cached data."
            : `Some analysis is unavailable (${[...state.failedAreas].join(", ") || "partial data"}). Official team data is still shown.`}
        </div>
      ) : null}

      <main id="main-content" className="content" tabIndex={-1}>{children}</main>

      <footer className="site-foot">
        <span>Fantasy Football AI is an independent, free tool. Not affiliated with or endorsed by the Premier League or Fantasy Premier League. It never changes your official team.</span>
        <span>Recommendations only.</span>
      </footer>

      <nav className="tabbar" aria-label="Mobile primary">
        {mobileItems.map((item) => {
          const Icon = ICONS[item.key];
          const active = isActive(item, pathname);
          return (
            <Link key={item.key} href={item.href} className="tab" aria-current={active ? "page" : undefined}>
              <Icon size={20} aria-hidden="true" />
              <span>{item.short}</span>
            </Link>
          );
        })}
        <button type="button" className="tab" aria-haspopup="dialog" aria-expanded={moreOpen} data-active={moreActive || undefined} onClick={() => setMoreOpen(true)}>
          <Menu size={20} aria-hidden="true" />
          <span>More</span>
        </button>
      </nav>

      <Sheet open={moreOpen} onClose={() => setMoreOpen(false)} title="More" subtitle="Research, history and settings">
        <nav className="more-nav" aria-label="More destinations">
          {moreItems.map((item) => {
            const Icon = ICONS[item.key];
            return (
              <Link key={item.key} href={item.href} className="more-link" aria-current={isActive(item, pathname) ? "page" : undefined} onClick={() => setMoreOpen(false)}>
                <Icon size={18} aria-hidden="true" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <p className="side-disclaimer">Fantasy Football AI is an independent, free tool. Not affiliated with or endorsed by the Premier League or Fantasy Premier League. It never changes your official team.</p>
      </Sheet>
    </div>
  );
}
