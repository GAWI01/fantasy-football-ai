"use client";

import { Database, LogOut, ShieldCheck, Sparkles, Tags } from "lucide-react";
import Link from "next/link";

import { useTeam } from "@/app/providers/TeamProvider";
import { Card, SourceBadge } from "@/components/ui/primitives";
import { API_BASE_URL } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { motionOptions, useMotionPreference, usePrefersReducedMotion, writeMotionPreference } from "@/lib/motion";
import { useDataLabels, writeDataLabels } from "@/lib/preferences";

const SOURCE_GUIDE: Array<{ kind: Parameters<typeof SourceBadge>[0]["kind"]; text: string }> = [
  { kind: "live", text: "Scores updating during a Gameweek. They can still change until bonus is confirmed." },
  { kind: "official", text: "Facts returned by the public FPL service: picks, prices, fixtures, points." },
  { kind: "model", text: "Projections from the Fantasy Football AI model. A forecast, never a result." },
  { kind: "derived", text: "Arithmetic on the above, such as transfer gain after a hit." },
  { kind: "cached", text: "The last good copy, shown when the official service did not respond." },
];

export function SettingsWorkspace() {
  const { teamId, dashboard, disconnect } = useTeam();
  const dataLabels = useDataLabels();
  const motion = useMotionPreference();
  const systemReduced = usePrefersReducedMotion();
  const modelVersion = dashboard?.meta.prediction_version ?? dashboard?.data.team.prediction_file ?? null;

  return (
    <div className="stack">
      <header className="page-head">
        <div>
          <span className="eyebrow">Account &amp; data</span>
          <h1>Settings</h1>
          <p className="page-lede">Your public Team ID is stored only in this browser. Fantasy Football AI never asks for an FPL password.</p>
        </div>
      </header>

      <div className="grid-2">
        <Card title="Connected team" icon={<Database size={16} />}>
          <dl className="kv">
            <div><dt>Public Team ID</dt><dd className="num">{teamId ?? "Not connected"}</dd></div>
            {dashboard ? <div><dt>Team</dt><dd>{dashboard.data.team.name}</dd></div> : null}
          </dl>
          <div className="row">
            {teamId ? (
              <button type="button" className="btn btn-sm btn-danger" onClick={disconnect}><LogOut size={14} aria-hidden="true" />Disconnect team</button>
            ) : <Link className="btn btn-sm btn-primary" href="/">Connect your team</Link>}
          </div>
        </Card>

        <Card title="Motion" icon={<Sparkles size={16} />}>
          <fieldset className="radio-list">
            <legend className="sr-only">How much the app moves</legend>
            {motionOptions.map((option) => (
              <label key={option.id} className={`radio-card${motion === option.id ? " is-active" : ""}`}>
                <input type="radio" name="motion" value={option.id} checked={motion === option.id} onChange={() => writeMotionPreference(option.id)} />
                <span><b>{option.label}</b><small>{option.description}</small></span>
              </label>
            ))}
          </fieldset>
          <p className="card-note">{systemReduced ? "Your device asks for reduced motion, so nothing moves whatever you choose here." : "Saved in this browser. Your device's reduce-motion setting always wins."}</p>
        </Card>

        <Card title="Data labels" icon={<Tags size={16} />}>
          <label className="check check-row">
            <input type="checkbox" checked={dataLabels} onChange={(event) => writeDataLabels(event.target.checked)} />
            <span><b>Show where each number comes from</b><small>Off keeps screens calm. Live and Cached always show, and forecasts always carry xP.</small></span>
          </label>
          <ul className="source-guide">
            {SOURCE_GUIDE.map((item) => <li key={item.kind}><SourceBadge kind={item.kind} always /><span>{item.text}</span></li>)}
          </ul>
          <details className="tech-details">
            <summary>Technical details</summary>
            <dl className="kv">
              <div><dt>API origin</dt><dd>{API_BASE_URL || "Same-origin gateway"}</dd></div>
              <div><dt>Model version</dt><dd>{modelVersion ?? "Unavailable"}</dd></div>
              <div><dt>Plan generated</dt><dd>{dashboard?.meta.generated_at ? dateTime(dashboard.meta.generated_at) : "Unavailable"}</dd></div>
            </dl>
          </details>
        </Card>
      </div>

      <Card title="What Fantasy Football AI can and cannot do" icon={<ShieldCheck size={16} />}>
        <p>Fantasy Football AI is a free, independent tool. It reads public manager data and gives decision support. It cannot make transfers, play chips or change your captain on the official game; every lineup and transfer on this site is a simulation until you make it yourself.</p>
        <p className="card-note">Not affiliated with or endorsed by the Premier League, Fantasy Premier League or any football club. Club colours are shown on simplified kits drawn for this site; they are not official designs or replicas. <Link href="/privacy">Privacy and terms</Link>.</p>
      </Card>
    </div>
  );
}
