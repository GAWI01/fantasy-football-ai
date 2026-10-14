"use client";

import { Download, Share, SquarePlus, X } from "lucide-react";
import { useState, useSyncExternalStore } from "react";

import { WELCOME_EVENT, WELCOME_KEY } from "@/components/overview/WelcomeTips";
import {
  currentPlatform, dismissInstall, isInstallDismissed, promptInstall, subscribeInstall, type InstallPlatform,
} from "@/lib/install";

function usePlatform(): InstallPlatform {
  // The server and first paint assume "installed", so nothing flashes before the browser is known.
  return useSyncExternalStore(subscribeInstall, currentPlatform, () => "installed");
}

function IosSteps() {
  return (
    <ol className="install-steps">
      <li><Share size={16} aria-hidden="true" /><span>Tap <b>Share</b> in Safari (on newer iPhones it sits under the <b>•••</b> button).</span></li>
      <li><SquarePlus size={16} aria-hidden="true" /><span>Choose <b>Add to Home Screen</b>, then <b>Add</b>.</span></li>
    </ol>
  );
}

/** The instructions or install button for this browser; null when there is nothing to do. */
function InstallBody({ platform }: { platform: InstallPlatform }) {
  const [busy, setBusy] = useState(false);
  if (platform === "prompt") {
    return (
      <button type="button" className="btn btn-sm btn-primary" disabled={busy}
        onClick={async () => { setBusy(true); try { await promptInstall(); } finally { setBusy(false); } }}>
        <Download size={16} aria-hidden="true" /> Install the app
      </button>
    );
  }
  if (platform === "ios-safari") return <IosSteps />;
  if (platform === "ios-other") {
    return <p>On iPhone only Safari can add apps to the Home Screen. Open this page in <b>Safari</b>, then use <b>Share → Add to Home Screen</b>.</p>;
  }
  return null;
}

const WHY = "It opens full screen from an icon, like an app. Nothing to download from a store, and no account.";

function welcomeSeen(): boolean {
  try { return window.localStorage.getItem(WELCOME_KEY) === "1"; } catch { return true; }
}

/** Home: a one-time card offering the app on the Home Screen, after the welcome tips are closed. */
export function InstallBanner() {
  const platform = usePlatform();
  const hidden = useSyncExternalStore(
    (onChange) => {
      const off = subscribeInstall(onChange);
      window.addEventListener(WELCOME_EVENT, onChange);
      return () => { off(); window.removeEventListener(WELCOME_EVENT, onChange); };
    },
    () => isInstallDismissed() || !welcomeSeen(),
    () => true,
  );
  if (hidden || platform === "installed" || platform === "unsupported") return null;
  return (
    <aside className="welcome install-card" aria-label="Add the app to your Home Screen">
      <div className="welcome-head">
        <b>Add FF·AI to your Home Screen</b>
        <button type="button" className="icon-btn" onClick={dismissInstall} aria-label="Hide this tip"><X size={16} aria-hidden="true" /></button>
      </div>
      <p className="install-why">{WHY}</p>
      <InstallBody platform={platform} />
    </aside>
  );
}

/** Settings: always available, so a closed banner is never the only way back. */
export function InstallSettings() {
  const platform = usePlatform();
  if (platform === "installed") return <p className="muted">FF·AI is running from your Home Screen.</p>;
  if (platform === "unsupported") {
    return <p className="muted">Open this site in Safari on iPhone, or Chrome on Android, to add it to your Home Screen.</p>;
  }
  return (
    <div className="install-settings">
      <p className="install-why">{WHY}</p>
      <InstallBody platform={platform} />
    </div>
  );
}
