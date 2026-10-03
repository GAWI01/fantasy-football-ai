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

const GROUP_LABEL = { decide: "Decide", research: "Research", account: "Account" } as const;


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

      <aside className="sidebar" aria-label="Sidebar">
        <Link href="/" className="brand" aria-label="FPL-AI overview">
          <BrandMark />
          <span className="brand-text"><strong>FPL-AI</strong><small>Gameweek intelligence</small></span>
        </Link>
        <nav className="side-nav" aria-label="Primary">
          {(["decide", "research", "account"] as const).map((group) => (
            <div className="side-group" key={group}>
              <span className="side-group-label">{GROUP_LABEL[group]}</span>
              {NAV_ITEMS.filter((item) => item.group === group).map((item) => {
                const Icon = ICONS[item.key];
                const active = isActive(item, pathname);
                return (
                  <Link key={item.key} href={item.href} className="side-link" aria-current={active ? "page" : undefined} title={item.label}>
                    <Icon size={18} aria-hidden="true" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="side-foot">
          {team ? (
            <Link href="/settings" className="team-card" aria-label={`Connected team ${team.name}. Open settings`}>
              <span className="team-card-mark" aria-hidden="true">{team.name.slice(0, 2).toUpperCase()}</span>
              <span className="team-card-text">
                <strong>{team.name}</strong>
                <small>{team.overall_rank ? `OR ${compact(team.overall_rank)}` : `Team ${teamId}`}</small>
              </span>
            </Link>
          ) : (
            <Link href="/" className="team-card team-card-empty">
              <span className="team-card-text"><strong>No team connected</strong><small>Add your public Team ID</small></span>
            </Link>
          )}
          <p className="side-disclaimer">Independent tool. Not affiliated with the Premier League or FPL.</p>
        </div>
      </aside>

      <div className="stage">
        <header className="topbar">
          <Link href="/" className="topbar-brand" aria-label="FPL-AI overview"><BrandMark size={28} /></Link>
          <PhaseChip state={state} connected={connected} />
          {showDeadline ? <DeadlineCountdown deadline={showDeadline} event={deadlineEvent} /> : null}
          <div className="topbar-end">
            {connected ? <Freshness generatedAt={state.generatedAt} stale={state.stale} /> : null}
            {connected ? (
              <button type="button" className="icon-btn" onClick={() => void refresh()} disabled={loading} aria-label={loading ? "Refreshing data" : "Refresh data"} title="Refresh data">
                <RefreshCw size={16} aria-hidden="true" className={loading ? "spin" : undefined} />
              </button>
            ) : null}
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
      </div>

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
        <p className="side-disclaimer">Independent tool. Not affiliated with the Premier League or FPL. FPL-AI never changes your official team.</p>
      </Sheet>
    </div>
  );
}
