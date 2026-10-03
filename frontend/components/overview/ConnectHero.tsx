"use client";

import { ArrowRight, CalendarRange, Crown, Lock, Radio, Repeat2, Users } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { useTeam } from "@/app/providers/TeamProvider";
import { BrandMark } from "@/components/shell/BrandMark";

/** A real public team people can open to see the cockpit before entering their own. */
const EXAMPLE_TEAM = { id: "665875", owner: "gawi" };

const PROMISES = [
  { icon: Repeat2, title: "Transfer or hold", text: "One clear call with the expected gain, hit cost and the alternative." },
  { icon: Crown, title: "Captain and lineup", text: "Armband, vice, best XI and bench order from the players you own." },
  { icon: Radio, title: "Live cockpit", text: "After the deadline: live points, captain return and who is left to play." },
];

export function ConnectHero() {
  const { connect, loading, error } = useTeam();
  const [value, setValue] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  async function open(id: string) {
    setLocalError(null);
    try { await connect(id); } catch { /* The provider exposes the API error. */ }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    const fromUrl = trimmed.match(/entry\/(\d+)/)?.[1];
    const id = fromUrl ?? trimmed;
    if (!/^\d{1,10}$/.test(id)) {
      setLocalError("Enter the number from your FPL team URL, e.g. 1234567.");
      return;
    }
    await open(id);
  }

  const message = localError ?? error;
  return (
    <div className="connect">
      <section className="connect-hero" aria-labelledby="connect-title">
        <div className="connect-copy">
          <span className="connect-brand"><BrandMark size={40} /><span className="eyebrow">Fantasy Football AI · Gameweek intelligence</span></span>
          <h1 id="connect-title">Know your move <span>before the deadline.</span></h1>
          <p>Connect your public team and Fantasy Football AI turns official data, model projections and an optimizer into one plan: transfer or hold, captain, bench and chip, with the reasons and the risk.</p>
          <form className="connect-form" onSubmit={submit} noValidate>
            <label htmlFor="team-id-input" className="field-label">Your FPL Team ID</label>
            <div className="connect-input-row">
              <input
                id="team-id-input"
                className="input"
                inputMode="numeric"
                autoComplete="off"
                placeholder="e.g. 1234567 or paste your team URL"
                value={value}
                onChange={(event) => setValue(event.target.value)}
                aria-invalid={message ? true : undefined}
                aria-describedby={message ? "team-id-error team-id-help" : "team-id-help"}
              />
              <button className="btn btn-primary" type="submit" disabled={loading || !value.trim()}>
                {loading ? "Connecting…" : "Open my cockpit"}
                <ArrowRight size={16} aria-hidden="true" />
              </button>
            </div>
            <p id="team-id-help" className="connect-help">Find it in your team’s web address: …/entry/<b>1234567</b>/event/…</p>
            <p className="connect-example">
              <span className="faint">Just looking?</span>
              <button type="button" className="example-chip" onClick={() => open(EXAMPLE_TEAM.id)} disabled={loading}>
                Try {EXAMPLE_TEAM.owner}’s team <span className="num">{EXAMPLE_TEAM.id}</span>
                <ArrowRight size={13} aria-hidden="true" />
              </button>
            </p>
            {message ? <p id="team-id-error" className="connect-error" role="alert">{message}</p> : null}
          </form>
          <p className="connect-trust"><Lock size={13} aria-hidden="true" /> Public data only. No password, and Fantasy Football AI never changes your official team.</p>
        </div>
        <ul className="connect-promises" aria-label="What you get">
          {PROMISES.map(({ icon: Icon, title, text }) => (
            <li key={title}>
              <span className="card-icon" aria-hidden="true"><Icon size={16} /></span>
              <div><strong>{title}</strong><p>{text}</p></div>
            </li>
          ))}
        </ul>
      </section>
      <nav className="connect-explore" aria-label="Explore without a team">
        <span className="faint">No Team ID handy?</span>
        <Link className="link" href="/players"><Users size={14} aria-hidden="true" />Browse players</Link>
        <Link className="link" href="/fixtures"><CalendarRange size={14} aria-hidden="true" />Fixture planner</Link>
      </nav>
    </div>
  );
}
