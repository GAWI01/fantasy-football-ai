"use client";

import { Compass, Home, Repeat2, X } from "lucide-react";
import { useSyncExternalStore } from "react";

export const WELCOME_KEY = "fpl-ai-welcome-done";
const WELCOME_EVENT = "fpl-ai-welcome-change";

function read(): boolean {
  try { return window.localStorage.getItem(WELCOME_KEY) === "1"; } catch { return false; }
}

function subscribe(onChange: () => void) {
  window.addEventListener(WELCOME_EVENT, onChange);
  return () => window.removeEventListener(WELCOME_EVENT, onChange);
}

/** Three lines for a first visit: where things are. Closed once, gone for good. */
export function WelcomeTips() {
  // Server render and first paint assume "seen", so the card never flashes for returning visitors.
  const seen = useSyncExternalStore(subscribe, read, () => true);
  if (seen) return null;
  const close = () => {
    try { window.localStorage.setItem(WELCOME_KEY, "1"); } catch { /* private mode: closes for this visit */ }
    window.dispatchEvent(new Event(WELCOME_EVENT));
  };
  return (
    <aside className="welcome" aria-label="How this app works">
      <div className="welcome-head">
        <b>New here? Three things to know</b>
        <button type="button" className="icon-btn" onClick={close} aria-label="Close tips"><X size={16} aria-hidden="true" /></button>
      </div>
      <ul>
        <li><Home size={16} aria-hidden="true" /><span><b>Home</b> tells you what to do this Gameweek. Tap a line for details.</span></li>
        <li><Repeat2 size={16} aria-hidden="true" /><span><b>Plan</b> explains the transfer, captain and chips, and lets you try your own swap.</span></li>
        <li><Compass size={16} aria-hidden="true" /><span><b>Explore</b> looks up any player, price change or fixture.</span></li>
      </ul>
      <p>Words with a <span className="term-sample">dotted line</span> explain themselves when you tap them. Nothing here changes your real team.</p>
      <button type="button" className="btn btn-sm btn-primary" onClick={close}>Got it</button>
    </aside>
  );
}
