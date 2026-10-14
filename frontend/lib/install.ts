/**
 * "Add to Home Screen" support. Chrome/Edge on Android and desktop offer a real
 * install prompt (`beforeinstallprompt`); iPhone Safari has none, so it gets
 * short instructions. Other iPhone browsers and in-app browsers cannot install
 * at all and are told to open the page in Safari.
 */
export type InstallPlatform = "installed" | "prompt" | "ios-safari" | "ios-other" | "unsupported";

type InstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: "accepted" | "dismissed" }> };

export const INSTALL_DISMISSED_KEY = "fpl-ai-install-dismissed";
const CHANGE = "fpl-ai-install-change";
let deferred: InstallPromptEvent | null = null;
let installed = false;
let dismissedThisVisit = false;

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault(); // keep it for our own button instead of the browser's mini-bar
    deferred = event as InstallPromptEvent;
    window.dispatchEvent(new Event(CHANGE));
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    installed = true;
    window.dispatchEvent(new Event(CHANGE));
  });
}

export function detectPlatform(nav: Pick<Navigator, "userAgent" | "maxTouchPoints"> & { standalone?: boolean },
  standaloneDisplay: boolean, hasPrompt: boolean): InstallPlatform {
  if (installed || standaloneDisplay || nav.standalone) return "installed";
  if (hasPrompt) return "prompt";
  const ua = nav.userAgent;
  // iPadOS reports a Mac user agent; touch points tell them apart.
  const ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && nav.maxTouchPoints > 1);
  if (!ios) return "unsupported";
  const otherBrowser = /CriOS|FxiOS|EdgiOS|OPiOS|GSA\/|FBAN|FBAV|Instagram|Snapchat|Line\/|TikTok|musical_ly/.test(ua);
  return otherBrowser ? "ios-other" : "ios-safari";
}

export function currentPlatform(): InstallPlatform {
  const standalone = window.matchMedia?.("(display-mode: standalone)").matches ?? false;
  return detectPlatform(window.navigator as Navigator & { standalone?: boolean }, standalone, deferred != null);
}

export function subscribeInstall(onChange: () => void) {
  window.addEventListener(CHANGE, onChange);
  return () => window.removeEventListener(CHANGE, onChange);
}

/** Shows the browser's install dialog; false when there is none to show. */
export async function promptInstall(): Promise<boolean> {
  if (!deferred) return false;
  const event = deferred;
  deferred = null;
  await event.prompt();
  const { outcome } = await event.userChoice;
  window.dispatchEvent(new Event(CHANGE));
  return outcome === "accepted";
}

export function isInstallDismissed(): boolean {
  if (dismissedThisVisit) return true;
  try { return window.localStorage.getItem(INSTALL_DISMISSED_KEY) === "1"; } catch { return false; }
}

export function dismissInstall() {
  dismissedThisVisit = true;
  try { window.localStorage.setItem(INSTALL_DISMISSED_KEY, "1"); } catch { /* private mode: hides for this visit */ }
  window.dispatchEvent(new Event(CHANGE));
}
