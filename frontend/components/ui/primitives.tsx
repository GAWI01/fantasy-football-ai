import type { ReactNode } from "react";

import type { SourceKind } from "@/lib/model/phase";

const SOURCE_COPY: Record<SourceKind, { label: string; hint: string }> = {
  live: { label: "Live", hint: "Live official match data for the Gameweek in progress. Can still change." },
  official: { label: "Official", hint: "Official FPL data for your public team." },
  model: { label: "Model", hint: "Fantasy Football AI model projection. A forecast, not a result." },
  derived: { label: "Derived", hint: "Calculated by Fantasy Football AI from official and model data." },
  cached: { label: "Cached", hint: "The official FPL service did not respond, so the last cached response is shown." },
};

export function SourceBadge({ kind, label }: { kind: SourceKind; label?: string }) {
  const copy = SOURCE_COPY[kind];
  return (
    <span className={`src src-${kind}`} title={copy.hint}>
      {kind === "live" ? <i className="src-pulse" aria-hidden="true" /> : null}
      {label ?? copy.label}
    </span>
  );
}

export function Card({
  title,
  eyebrow,
  source,
  action,
  children,
  className,
  id,
  icon,
  labelledBy,
  tone,
}: {
  title?: ReactNode;
  eyebrow?: ReactNode;
  source?: SourceKind | SourceKind[];
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
  icon?: ReactNode;
  labelledBy?: string;
  tone?: "accent" | "live" | "warn" | "risk";
}) {
  const sources = source ? (Array.isArray(source) ? source : [source]) : [];
  const headingId = labelledBy ?? (id ? `${id}-title` : undefined);
  return (
    <section className={["card", tone ? `card-${tone}` : "", className].filter(Boolean).join(" ")} id={id} aria-labelledby={title && headingId ? headingId : undefined}>
      {title || action || sources.length ? (
        <header className="card-head">
          <div className="card-title">
            {icon ? <span className="card-icon" aria-hidden="true">{icon}</span> : null}
            <div>
              {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
              {title ? <h2 id={headingId}>{title}</h2> : null}
            </div>
          </div>
          <div className="card-meta">
            {sources.map((kind) => <SourceBadge key={kind} kind={kind} />)}
            {action}
          </div>
        </header>
      ) : null}
      {children}
    </section>
  );
}

export function Stat({
  label,
  value,
  unit,
  sub,
  source,
  tone,
  size = "md",
}: {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  sub?: ReactNode;
  source?: SourceKind;
  tone?: "pos" | "neg" | "warn" | "accent" | "live";
  size?: "sm" | "md" | "lg" | "xl";
}) {
  return (
    <div className={`stat stat-${size}`}>
      <span className="stat-label">{label}{source ? <SourceBadge kind={source} /> : null}</span>
      <strong className={["stat-value", tone ? `tone-${tone}` : ""].filter(Boolean).join(" ")}>
        {value}{unit ? <small className="stat-unit">{unit}</small> : null}
      </strong>
      {sub ? <span className="stat-sub">{sub}</span> : null}
    </div>
  );
}

export function Delta({ value, digits = 1, unit, neutralBelow = 0.05 }: { value: number | null | undefined; digits?: number; unit?: string; neutralBelow?: number }) {
  if (typeof value !== "number" || !Number.isFinite(value)) return <span className="delta">—</span>;
  const tone = Math.abs(value) < neutralBelow ? "flat" : value > 0 ? "pos" : "neg";
  const text = tone === "flat" ? (0).toFixed(digits) : `${value > 0 ? "+" : "−"}${Math.abs(value).toFixed(digits)}`;
  return <span className={`delta delta-${tone}`}>{text}{unit ? <small>{unit}</small> : null}</span>;
}

export function Meter({ value, tone = "accent", label }: { value: number | null | undefined; tone?: "accent" | "pos" | "warn" | "neg" | "live"; label: string }) {
  const clamped = typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : null;
  return (
    <span className={`meter meter-${tone}`} role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={clamped == null ? undefined : Math.round(clamped * 100)}>
      <i style={{ width: `${(clamped ?? 0) * 100}%` }} />
    </span>
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  size = "md",
}: {
  options: Array<{ value: T; label: ReactNode; disabled?: boolean }>;
  value: T;
  onChange: (value: T) => void;
  label: string;
  size?: "sm" | "md";
}) {
  return (
    <div className={`seg seg-${size}`} role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          disabled={option.disabled}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Skeleton({ lines = 3, height }: { lines?: number; height?: number }) {
  return (
    <div className="skeleton" aria-hidden="true" style={height ? { minHeight: height } : undefined}>
      {Array.from({ length: lines }, (_, index) => <i key={index} />)}
    </div>
  );
}

export function FdrChip({ difficulty, children, title }: { difficulty: number | null | undefined; children: ReactNode; title?: string }) {
  const level = typeof difficulty === "number" ? Math.max(1, Math.min(5, Math.round(difficulty))) : 0;
  return <span className={`fdr fdr-${level}`} title={title ?? (level ? `Difficulty ${difficulty}` : "No fixture")}>{children}</span>;
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="kbd">{children}</kbd>;
}
