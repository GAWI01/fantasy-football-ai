import { AlertTriangle, CircleSlash, Clock3, Info, Loader2, WifiOff } from "lucide-react";
import type { ReactNode } from "react";

export type DataStateTone = "neutral" | "warning" | "error" | "empty" | "stale" | "unavailable";

const ICONS: Record<DataStateTone, typeof Info> = {
  neutral: Info,
  warning: AlertTriangle,
  error: WifiOff,
  empty: CircleSlash,
  stale: Clock3,
  unavailable: CircleSlash,
};

/**
 * One accessible surface for LOADING / EMPTY / STALE / ERROR / UNAVAILABLE states.
 * Errors are announced assertively; everything else politely.
 */
export function DataState({
  title,
  children,
  tone = "neutral",
  loading = false,
  action,
  compact = false,
}: {
  title: string;
  children?: ReactNode;
  tone?: DataStateTone;
  loading?: boolean;
  action?: ReactNode;
  compact?: boolean;
}) {
  const Icon = loading ? Loader2 : ICONS[tone];
  return (
    <section
      className={["data-state", `data-state-${loading ? "loading" : tone}`, compact ? "data-state-compact" : ""].filter(Boolean).join(" ")}
      role={tone === "error" ? "alert" : "status"}
      aria-busy={loading || undefined}
    >
      <span className="data-state-icon" aria-hidden="true"><Icon size={compact ? 15 : 18} /></span>
      <div className="data-state-body">
        <strong>{title}</strong>
        {children ? <div className="data-state-text">{children}</div> : null}
        {loading ? <div className="data-state-skeleton" aria-hidden="true"><i /><i /><i /></div> : null}
        {action ? <div className="data-state-action">{action}</div> : null}
      </div>
    </section>
  );
}
